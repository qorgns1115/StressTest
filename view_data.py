import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import time
import json
from datetime import datetime
import base64

def load_test_results(base_dir):
    """각 phase 폴더에서 테스트 결과를 로드하여 DataFrame으로 변환"""
    all_results = []
    
    for folder in os.listdir(base_dir):
        if folder.startswith('phase_'):
            # 스레드 수 추출
            thread_count = int(folder.split('_')[1])
            
            # phase 폴더 내의 stats 파일 찾기
            phase_dir = os.path.join(base_dir, folder)
            stats_files = [f for f in os.listdir(phase_dir) if f.startswith('test_results_')]
            
            if stats_files:
                # 가장 최근 stats 파일 사용
                latest_stats = stats_files[-1]
                with open(os.path.join(phase_dir, latest_stats), 'r') as f:
                    stats = json.load(f)
                    stats['thread_count'] = thread_count
                    all_results.append(stats)
    
    return pd.DataFrame(all_results)


def get_download_link(df, filename):
    """데이터프레임을 다운로드 링크로 변환"""
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">Download {filename}</a>'

    return href

def main():
    st.set_page_config(page_title="API Performance Dashboard", layout="wide")

    st.title("🚀 API Performance Test Dashboard")
    with st.sidebar:
        st.header("Dashboard Settings")
        error_threshold = st.slider(
            "Error Rate Threshold (%)",
            min_value=0.0,
            max_value=10.0,
            value=5.0,
            step=0.1
        )

        response_time_threshold = st.slider(
            "Response Time Threshold (ms)",
            min_value=0,
            max_value=10000,
            value=5000,
            step=100
        )

        auto_refresh = st.checkbox("Enable Auto Refresh", value=False)
        if (auto_refresh):
            refresh_interval = st.slider(
                "Refresh Interval (seconds)",
                min_value=5,
                max_value=300,
                value=30
            )

    # select result repo
    result_dirs = [d for d in os.listdir('.') if d.startswith('stress_test_results_')]
    if not result_dirs:
        st.error("No test results found!")
        return
        
    selected_dir = st.selectbox(
        "Select Test Run:",
        options=result_dirs,
        index=len(result_dirs)-1  # default the newest version
    )
    
    # load data
    df = load_test_results(selected_dir)
    
    # the top result matrics
    def load_and_display_data():
        latest_results = df.iloc[-1]
        csv_filename = f"test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        left, right = st.columns([7, 1])
        # CSV 다운로드 버튼
        with right: 
            st.download_button(
                label="📥 Download CSV",
                data=df.to_csv(index=False).encode('utf-8'),
                file_name=csv_filename,
                mime='text/csv'
            )

        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Total Requests",
                f"{int(latest_results['total_requests']):,}",
                delta=None
            )
            
        with col2:
            error_rate = latest_results['error_rate']
            st.metric(
                "Error Rate",
                f"{latest_results['error_rate']:.2f}%",
                delta=None,
                delta_color="inverse"
            )
            if error_rate > error_threshold:
                st.warning("⚠️ Error rate exceeds threshold!")
            
        with col3:
            avg_response = latest_results["avg_response_time"]
            st.metric(
                "Avg Response Time",
                f"{avg_response:.2f}ms",
                delta=None,
                delta_color="inverse"
            )
            
        with col4:
            st.metric(
                "Requests/Second",
                f"{latest_results['requests_per_second']:.2f}",
                delta=None
            )
        
        # for charts
        tab1, tab2, tab3 = st.tabs(["📈 Performance Trends", "📊 Response Time Analysis", "❌ Error Analysis"])
        
        with tab1:
            # Performance Trends Graph
            fig = go.Figure()
            
            # Response Time Analysis
            fig.add_trace(go.Scatter(
                x=df['thread_count'],
                y=df['avg_response_time'],
                name='Avg Response Time (ms)',
                line=dict(color='#1f77b4')
            ))

            fig.add_hline(
                y=response_time_threshold,
                line_dash="dash",
                line_color="red",
                annotation_text="Response Time Threshold"
            )
            
            # y-axis
            fig.add_trace(go.Scatter(
                x=df['thread_count'],
                y=df['error_rate'],
                name='Error Rate (%)',
                line=dict(color='#d62728'),
                yaxis='y2'
            ))

            fig.update_layout(
                title='Performance Metrics by Thread Count',
                xaxis=dict(title='Thread Count'),
                yaxis=dict(title='Response Time (ms)'),
                yaxis2=dict(title='Error Rate (%)', overlaying='y', side='right'),
                legend=dict(x=0.02, y=0.98),
                hovermode='x unified'
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
        with tab2:
            # Response Time Analysis
            response_time_df = pd.DataFrame({
                'Thread Count': df['thread_count'],
                'Min': df['min_response_time'],
                'Avg': df['avg_response_time'],
                '90th': df['90th_percentile'],
                '95th': df['95th_percentile'],
                'Max': df['max_response_time']
            })
            
            fig_box = px.box(
                response_time_df.melt(id_vars=['Thread Count'], 
                                    var_name='Metric', 
                                    value_name='Response Time (ms)'),
                x='Thread Count',
                y='Response Time (ms)',
                color='Metric',
                title='Response Time Distribution'
            )

            fig_box.add_hline(
                y=response_time_threshold,
                line_dash="dash",
                line_color="red",
                annotation_text="Response Time Threshold"
            )

            st.plotly_chart(fig_box, use_container_width=True)
            
        with tab3:
            # Error Analysis
            col1, col2 = st.columns(2)
            
            with col1:
                # Error Rate Trend
                fig_error = px.line(
                    df,
                    x='thread_count',
                    y='error_rate',
                    title='Error Rate Trend',
                    labels={'thread_count': 'Thread Count', 'error_rate': 'Error Rate (%)'}
                )

                fig_error.add_hline(
                    y=error_threshold,
                    line_dash="dash",
                    line_color="red",
                    annotation_text="Error Rate Threshold"
                )

                st.plotly_chart(fig_error, use_container_width=True)
                
            with col2:
                # Request Status Distribution
                latest = df.iloc[-1]
                success_count = latest['total_requests'] - latest['error_count']
                
                fig_pie = px.pie(
                    values=[success_count, latest['error_count']],
                    names=['Success', 'Error'],
                    title='Request Status Distribution'
                )
                st.plotly_chart(fig_pie, use_container_width=True)
                
    load_and_display_data()
    # Detailed Test Results
    st.subheader("📋 Detailed Test Results")
    st.dataframe(
        df.style.format({
            'error_rate': '{:.2f}%',
            'avg_response_time': '{:.2f}ms',
            'requests_per_second': '{:.2f}',
            '90th_percentile': '{:.2f}',
            '95th_percentile': '{:.2f}'
        })
    )


if __name__ == "__main__":
    main()