import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import json
from datetime import datetime
import base64

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
    
    return data

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
   
def detect_changes(data):
    """변화 감지 함수"""
    changes = {
        'thread_changes': len(data['thread_count'].unique()) > 1,
        'duration_changes': len(data['duration'].unique()) > 1,
        'latest_thread': data['thread_count'].iloc[-1],
        'latest_duration': data['duration'].iloc[-1]
    }
    return changes

def create_heatmap(data, metric):
    """스레드 수와 지속 시간에 따른 히트맵 생성"""
    pivot_data = data.pivot_table(
        values=metric,
        index='thread_count',
        columns='duration',
        aggfunc='mean'
    )
    
    fig = go.Figure(data=go.Heatmap(
        z=pivot_data.values,
        x=pivot_data.columns,
        y=pivot_data.index,
        colorscale='Viridis'
    ))
    
    fig.update_layout(
        title=f'{metric} Heatmap (Thread Count vs Duration)',
        xaxis_title='Duration (seconds)',
        yaxis_title='Thread Count',
    )
    return fig

def main():
    st.set_page_config(page_title="API Performance Dashboard", layout="wide")
    st.title("🚀 API Performance Test Dashboard")
    
    # 파일 선택
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

    changes = detect_changes(data)

    st.sidebar.subheader("Current Test Status")
    st.sidebar.info(f"""Latest Thread Count: {changes['latest_thread']}
    Latest Duration: {changes['latest_duration']} seconds
    Thread Count Changing: {'Yes' if changes['thread_changes'] else 'No'}
    Duration Changing: {'Yes' if changes['duration_changes'] else 'No'}
    """
    )

    st.subheader("Performance Heatmaps")
    col1, col2 = st.columns(2)

    with col1: 
        fig_requests_heatmap = create_heatmap(data, 'total_requests')
        st.plotly_chart(fig_requests_heatmap, use_container_width=True)
    
    with col2:
        fig_response_heatmap = create_heatmap(data, 'avg_response_time')
        st.plotly_chart(fig_response_heatmap, use_container_width=True)

    st.subheader("Time Series Metrics")
    fig_timeline = go.Figure()

    fig_timeline.add_trace(go.Scatter(
        x=data['timestamp'],
        y=data['thread_count'],
        mode="lines+markers",
        name='Thread Count',
        yaxis='y2'
    ))

    fig_timeline.add_trace(go.Scatter(
        x=data['timestamp'],
        y=data['avg_response_time'],
        mode='lines+markers',
        name='Avg Response Time'
    ))

        
    fig_timeline.update_layout(
        title='Thread Count and Response Time Over Time',
        xaxis_title='Time',
        yaxis_title='Response Time (ms)',
        yaxis2=dict(
            title='Thread Count',
            overlaying='y',
            side='right'
        )
    )
    
    st.plotly_chart(fig_timeline, use_container_width=True)

    # 상세 메트릭스 테이블
    st.subheader("Detailed Metrics")
    metrics_df = data[[
        'timestamp', 'thread_count', 'duration', 'total_requests',
        'error_count', 'error_rate', 'avg_response_time', 'requests_per_second'
    ]].sort_values('timestamp')
    
    st.dataframe(metrics_df)

    # 스레드 수 필터링
    unique_threads = sorted(data['thread_count'].unique())
    selected_thread = st.sidebar.selectbox(
        "Select Thread Count",
        unique_threads,
        index=len(unique_threads)-1
    )
    
    filtered_data = data[data['thread_count'] == selected_thread]

    # 대시보드 레이아웃
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Request Metrics by Duration")
        fig_requests = go.Figure()
        fig_requests.add_trace(go.Scatter(
            x=filtered_data['duration'],
            y=filtered_data['total_requests'],
            mode='lines+markers',
            name='Total Requests'
        ))
        fig_requests.add_trace(go.Scatter(
            x=filtered_data['duration'],
            y=filtered_data['error_count'],
            mode='lines+markers',
            name='Error Count'
        ))
        fig_requests.update_layout(
            title=f'Requests and Errors by Duration (Threads: {selected_thread})',
            xaxis_title='Duration (seconds)',
            yaxis_title='Count'
        )
        st.plotly_chart(fig_requests, use_container_width=True)

    with col2:
        st.subheader("Response Time Metrics")
        fig_response = go.Figure()
        fig_response.add_trace(go.Scatter(
            x=filtered_data['duration'],
            y=filtered_data['avg_response_time'],
            mode='lines+markers',
            name='Average'
        ))
        fig_response.add_trace(go.Scatter(
            x=filtered_data['duration'],
            y=filtered_data['95th_percentile'],
            mode='lines+markers',
            name='95th Percentile'
        ))
        fig_response.update_layout(
            title=f'Response Time by Duration (Threads: {selected_thread})',
            xaxis_title='Duration (seconds)',
            yaxis_title='Response Time (ms)'
        )
        st.plotly_chart(fig_response, use_container_width=True)

    # 엔드포인트별 성능
    st.subheader("Endpoint Performance")
    endpoint_df = create_endpoint_metrics(filtered_data)
    
    fig_endpoint = px.line(
        endpoint_df,
        x='duration',
        y='error_rate',
        color='endpoint',
        title=f'Error Rate by Endpoint and Duration (Threads: {selected_thread})'
    )
    fig_endpoint.update_layout(
        xaxis_title='Duration (seconds)',
        yaxis_title='Error Rate (%)'
    )
    st.plotly_chart(fig_endpoint, use_container_width=True)

    # 상세 메트릭스 테이블
    st.subheader("Detailed Metrics")
    metrics_df = filtered_data[[
        'duration', 'total_requests', 'error_count',
        'error_rate', 'avg_response_time', '95th_percentile', 'requests_per_second'
    ]].sort_values('duration')
    
    st.dataframe(metrics_df)

    # 자동 새로고침 설정
    st.sidebar.title("Dashboard Settings")
    refresh_rate = st.sidebar.selectbox(
        "Auto-refresh interval (seconds)",
        options=[0, 5, 10, 30, 60],
        index=0
    )
    
    if refresh_rate > 0:
        st.experimental_rerun()

if __name__ == "__main__":
    main()