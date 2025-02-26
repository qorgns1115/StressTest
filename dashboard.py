import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import json
from datetime import datetime

# 스크립트 시작 시 가장 먼저 설정
st.set_page_config(page_title="Load Test Results", layout="wide")
st.title("📊 Load Test Performance Analysis")

def load_test_results(base_dir):
    """각 phase 폴더의 모든 JSON 파일을 로드하여 DataFrame으로 변환"""
    all_results = []
    
    for folder in os.listdir(base_dir):
        if folder.startswith('phase_threads_'):
            thread_count = int(folder.split('_')[2])
            duration = int(folder.split('_')[4])
            
            phase_dir = os.path.join(base_dir, folder)
            for stats_file in os.listdir(phase_dir):
                if stats_file.startswith('test_results_'):
                    with open(os.path.join(phase_dir, stats_file), 'r') as f:
                        stats = json.load(f)
                        stats['thread_count'] = thread_count
                        stats['duration'] = duration
                        stats['file_name'] = stats_file
                        all_results.append(stats)
    
    if not all_results:
        return None

    data = pd.DataFrame(all_results)
    data['timestamp'] = pd.to_datetime(data['timestamp'])
    
    # response_time과 throughput 데이터 처리
    data['min_response_time'] = data['response_time'].apply(lambda x: x['min'])
    data['max_response_time'] = data['response_time'].apply(lambda x: x['max'])
    data['avg_response_time'] = data['response_time'].apply(lambda x: x['mean'])
    data['median_response_time'] = data['response_time'].apply(lambda x: x['median'])
    data['90th_percentile'] = data['response_time'].apply(lambda x: x['90th_percentile'])
    data['95th_percentile'] = data['response_time'].apply(lambda x: x['95th_percentile'])
    data['99th_percentile'] = data['response_time'].apply(lambda x: x['99th_percentile'])
    data['requests_per_second'] = data['throughput'].apply(lambda x: x['requests_per_second'])
    data['error_rate'] = (data['error_count'] / data['total_requests'] * 100).round(2)
    
    return data.sort_values('duration')

def create_endpoint_metrics(data):
    """엔드포인트별 메트릭스 생성"""
    endpoint_data = []
    for _, row in data.iterrows():
        for endpoint, stats in row['endpoint_statistics'].items():
            endpoint_data.append({
                'timestamp': row['timestamp'],
                'thread_count': row['thread_count'],
                'duration': row['duration'],
                'endpoint': endpoint,
                'total_requests': stats['total_requests'],
                'error_rate': stats['error_rate'],
                'avg_response_time': stats['avg_response_time'],
                '90th_percentile': stats['90th_percentile'],
                'error_count': stats['error_count']
            })
    return pd.DataFrame(endpoint_data)

def create_performance_dashboard(data):
    
    divided1, divided2 = st.columns([4, 1])
    with divided1: 
        # Summary Statistics
        st.header("🔍 Test Configuration Range")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Thread Range", f"{data['thread_count'].min()} - {data['thread_count'].max()}")
        with col2:
            st.metric("Duration Range", f"{data['duration'].min()} - {data['duration'].max()} seconds")

    with divided2:
        st.markdown("### Export Data")
        csv_filename = f"test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        st.download_button(
            label="📥 Download CSV",
            data=data.to_csv(index=False).encode('utf-8'),
            file_name=csv_filename,
            mime="text/csv"
        )

    # metrics dataframe
    metrics_df = data.groupby(['thread_count', 'duration']).agg({
        'avg_response_time': 'mean',
        'requests_per_second': 'mean',
        'error_rate': 'mean',
        '95th_percentile': 'mean'
    }).round(2).reset_index()

    # 5. Optimal Configuration Finder
    st.header("🎯 Optimal Configuration Analysis")
    st.write("Based on response time and throughput:")
    
    best_throughput = metrics_df.loc[metrics_df['requests_per_second'].idxmax()]
    best_response = metrics_df.loc[metrics_df['avg_response_time'].idxmin()]
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Best Throughput Configuration")
        st.write(f"Threads: {best_throughput['thread_count']}")
        st.write(f"Duration: {best_throughput['duration']}s")
        st.write(f"Throughput: {best_throughput['requests_per_second']} req/s")
        
    with col2:
        st.subheader("Best Response Time Configuration")
        st.write(f"Threads: {best_response['thread_count']}")
        st.write(f"Duration: {best_response['duration']}s")
        st.write(f"Response Time: {best_response['avg_response_time']}ms")


    st.header("📑 Detailed Performance Metrics")
    st.dataframe(metrics_df.sort_values(['thread_count', 'duration']))

    return best_response

def main():
    # 파일 선택
    # result_dirs = 'stress_test_results_20250219_134529'
    result_dirs = [d for d in os.listdir('.') if d.startswith('stress_test_results')]
    if not result_dirs:
        st.error("No test result files found!")
        return
    
    selected_dir = st.selectbox("Select Test Run:", options=result_dirs, index=len(result_dirs)-1)
    
    # 데이터 로드
    data = load_test_results(selected_dir)
    if data is None:
        st.error("No data found in the selected directory!")
        return
        
    best_response = create_performance_dashboard(data)

    filtered_data = data[data['duration'] > 0].sort_values(by='thread_count')

    filtered_data['performance_status'] = pd.cut(
    filtered_data['error_rate'], 
    bins=[0, 1, 5, 100], 
    labels=['Good', 'Warning', 'Critical'])

    # 추가 분석 섹션
    st.subheader("Load Test Detailed Analysis")
    tabs = st.tabs(["Throughput Analysis", "Error Rate Analysis"])

    threshold = 10
    threshold_filtered_data = data[data['error_rate'] <= threshold]
    threshold_filtered_data['thread_count'] = threshold_filtered_data['thread_count'].astype(str)

    with tabs[0]:
        # 처리량 분석
        fig_throughput = px.line(
            filtered_data,
            x='thread_count',
            y='requests_per_second',
            color='duration',
            hover_data=['duration'],
            title='Throughput and Duration by Thread (Requests per Second)',
            markers=True,
        )

        fig_throughput.update_xaxes(type='category')

        fig_throughput.update_layout(
            xaxis_title='Thread Count',
            yaxis_title='Requests per Second'
        )
        st.plotly_chart(fig_throughput, use_container_width=True)

    with tabs[1]:        
        # 에러율 분석
        fig_errors = px.bar(
            threshold_filtered_data,
            x='thread_count',
            y='error_rate',
            color='duration',
            text='error_rate',
            barmode='group',
            title='Error Rate by Thread and Duration',
            category_orders={"thread_count": sorted(threshold_filtered_data['thread_count'].astype(int).unique())}
        )

        fig_errors.update_xaxes(type='category')

        fig_errors.update_traces(
            texttemplate='%{text:.2f}%',
            textposition='outside',
            width=0.2 
        )

        fig_errors.update_layout(
            height=600,
            bargap=0.2,
            bargroupgap=0.1,
            xaxis=dict(
                title="Thread Count",
                tickmode="linear"
            ),
            yaxis=dict(
                range=[0, 100],
                title="Error Rate(%)"),
            legend_title="Duration(seconds)"
        )

        fig_errors.add_hline(y=threshold, line_dash='dot', line_color='red', annotation_text=f"{threshold}% Threshold" )
        st.plotly_chart(fig_errors, use_container_width=True)

    # Endpoint Performance
    st.subheader("Endpoint Performance")
    endpoint_df = create_endpoint_metrics(filtered_data)
    best_thread = best_response['thread_count']

    best_thread_endpoints = endpoint_df[endpoint_df['thread_count'] == best_thread] # proper data
    best_thread_endpoints = best_thread_endpoints.sort_values(by='duration')
    best_thread_endpoints['error_rate'] = best_thread_endpoints['error_rate'].replace(0, 0.1)

    fig_endpoint = px.bar(
        best_thread_endpoints,
        x='duration',
        y='error_rate',
        color='endpoint',
        barmode='group',
        title=f"Error Rate by Endpoint and Duration (Best Response Time Threads: {best_thread_endpoints['thread_count'].values[0]})",
    )

    fig_endpoint.update_xaxes(type='category')
    
    fig_endpoint.update_layout(
        xaxis_title='Duration (seconds)',
        yaxis_title='Error Rate(%)',
        xaxis=dict(tickmode='linear'),
        yaxis=dict(range=[0, 100])
    )

    st.plotly_chart(fig_endpoint, use_container_width=True)

if __name__ == "__main__":
    main()