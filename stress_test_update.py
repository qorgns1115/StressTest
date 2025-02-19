import subprocess
import json
import time
import pandas as pd
import os
from datetime import datetime
import requests
from typing import Dict, Tuple, Optional
import numpy as np
from json import JSONEncoder

class NumpyEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return super(NumpyEncoder, self).default(obj)


# API 엔드포인트 및 HTTP 메서드 설정
API_ENDPOINTS = {
    "/v1/user/verify": "POST",
    "/v1/system/health": "GET",
    "/v1/comms/member": "POST",
    "/v1/comms/mobile-join": "POST",
    "/v1/comms/mobile-usage": "POST",
    "/v1/comms/mobile-bills": "POST",
    "/v1/comms/mobile-payments": "POST"
}

# 엔드포인트별 Header 설정
ENDPOINT_HEADERS = {
    "/v1/user/verify": {
        "X-Api-Tx-Id": "12345",
        "X-Src-Inst-Cd": "SRC001",
        "X-Dst-Inst-Cd": "DST001",
        "Content-Type": "application/json"
    },
    "/v1/system/health": {
        "X-Api-Tx-Id": "12345"
    },
    "default": {
        "X-Api-Tx-Id": "12345",
        "X-Src-Inst-Cd": "SRC001",
        "X-Dst-Inst-Cd": "DST001",
        "X-Api-Type": "application/json",
        "Content-Type": "application/json"
    }
}

# Request Bodies 설정
REQUEST_BODIES = {
    "/v1/user/verify": '{"user_id": "test_user"}',
    "/v1/comms/member": '{"user_id": "test_user", "search_timestamp": "2025-02-10", "next_page": "2000","limit": 1}',
    "/v1/comms/mobile-join": '{"user_id": "test_id", "search_timestamp": "2025-02-10", "ctrt_mng_no": "100001"}',
    "/v1/comms/mobile-usage": '{"user_id": "test_user", "search_timestamp": "2025-02-10", "ctrt_mng_no": "20", "bgng_ym": "2024-12", "end_ym": "2025-01"}',
    "/v1/comms/mobile-bills": '{"user_id": "test_user", "search_timestamp": "2025-02-10", "ctrt_mng_no": "20", "bgng_ym": "2024-12", "end_ym": "2025-01"}',
    "/v1/comms/mobile-payments": '{"user_id": "test_user", "search_timestamp": "2025-02-10", "ctrt_mng_no": "20", "bgng_ym": "2024-12", "end_ym": "2025-01"}'
}

# JMeter 실행 경로
JMETER_PATH = r"C:\Users\Administrator\Downloads\apache-jmeter-5.6.3\apache-jmeter-5.6.3\bin\jmeter.bat"

def run_jmeter_test(jmx_file, results_dir):
    """
    JMeter 테스트 실행
    :param jmx_file: JMeter 테스트 설정 파일 경로
    :param results_dir: 결과 저장 디렉토리
    :return: (성공 여부, 결과 파일 경로)
    """
    result_file = os.path.join(results_dir, "test_results.jtl")
    log_file = os.path.join(results_dir, "jmeter.log")
    
    print(f"🚀 JMeter 테스트 실행 중...")
    print(f"📁 결과 디렉토리: {results_dir}")
    
    cmd = f'"{JMETER_PATH}" -n -t "{jmx_file}" -l "{result_file}" -j "{log_file}"'
    
    try:
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                print(output.strip())
        
        return_code = process.poll()
        
        if return_code == 0:
            print("✅ JMeter 테스트 완료!")
            return True, result_file
        else:
            print(f"❌ JMeter 실행 실패 (반환 코드: {return_code})")
            return False, None
            
    except Exception as e:
        print(f"❌ 오류 발생: {str(e)}")
        return False, None
    
def load_config(config_file='stresstest_config.json'):
    """설정 파일에서 테스트 구성 로드"""
    try:
        with open(config_file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ 설정 파일을 찾을 수 없습니다: {config_file}")
        exit(1)
    except json.JSONDecodeError:
        print(f"❌ 설정 파일 형식이 잘못되었습니다: {config_file}")
        exit(1)

class StressTestController:
    def __init__(self, config):
        """
        스트레스 테스트 컨트롤러 초기화
        """
        self.initial_threads = config['test_parameters']['initial_threads']
        self.thread_increment = config['test_parameters']['thread_increment']
        self.max_threads = config['test_parameters']['max_threads']
        self.error_threshold = config['test_parameters']['error_threshold']
        self.response_time_threshold = config['test_parameters']['response_time_threshold']
        self.initial_duration = config['test_parameters']['initial_duration']
        self.duration_increment = config['test_parameters']['duration_increment']
        self.max_duration = config['test_parameters']['max_duration']
        
        self.current_threads = self.initial_threads
        self.current_duration = self.initial_duration
        self.test_phase = "running"
        self.failure_detected = False
        self.failure_reason = None
        
    def should_continue(self, stats: Dict) -> Tuple[bool, Optional[str]]:
        """
        테스트 지속 여부 결정
        """
        # max thread에서 임계값 초과하면 테스트 종료
        if self.current_threads >= self.max_threads:
            if stats["error_rate"] > self.error_threshold:
                return False, f"최대 쓰레드 수({self.max_threads})에서 오류율({stats['error_rate']}%)이 임계값({self.error_threshold}%)을 초과함"
            if stats["avg_response_time"] > self.response_time_threshold:
                return False, f"최대 쓰레드 수({self.max_threads})에서 응답시간({stats['avg_response_time']}ms)이 임계값({self.response_time_threshold}ms)을 초과함"
            
        # max thread & max duration 도달 시 종료
        if self.current_threads >= self.max_threads and self.current_duration >= self.max_duration:
            return False, f"최대 쓰레드 수({self.max_threads})와 최대 지속시간({self.max_duration}초)에 도달함"
            
        # 그 외의 경우 임계값 초과 시 thread 증가를 위한 시그널 반환
        if stats["error_rate"] > self.error_threshold:
            print(f"⚠️ 오류율({stats['error_rate']}%)이 임계값({self.error_threshold}%)을 초과함")
            return True, "threshold_exceeded"
        
        if stats["avg_response_time"] > self.response_time_threshold:
            print(f"⚠️ 응답시간({stats['avg_response_time']}ms)이 임계값({self.response_time_threshold}ms)을 초과함")
            return True, "threshold_exceeded"
            
        return True, None

    def increment_test_parameters(self, threshold_exceeded=False):
        """다음 테스트를 위한 파라미터 조정"""
        if threshold_exceeded:
            # 임계값 초과 시 duration 초기화하고 thread 증가
            self.current_duration = self.initial_duration
            if self.current_threads < self.max_threads:
                self.current_threads += self.thread_increment
            return "threads_increased"
        
        # 정상적인 경우 duration 증가
        if self.current_duration < self.max_duration:
            self.current_duration += self.duration_increment
        else:
            self.current_duration = self.initial_duration
            if self.current_threads < self.max_threads:
                self.current_threads += self.thread_increment
            return "threads_increased"


def create_jmx_file(config, results_dir, thread_count, duration, filename="generated_test.jmx"):
    """JMeter 테스트 설정 파일 생성"""
    full_path = os.path.join(results_dir, filename)
    
    # (이전 JMX 템플릿 코드는 동일하게 유지하되, duration 값만 변경)
    # ThreadGroup 설정에서 duration 값을 변경:
    # <stringProp name="ThreadGroup.duration">{duration}</stringProp>
    jmx_template = f'''<?xml version="1.0" encoding="UTF-8"?>
<jmeterTestPlan version="1.2" properties="5.0" jmeter="5.6.3">
  <hashTree>
    <TestPlan guiclass="TestPlanGui" testclass="TestPlan" testname="Stress Test Plan" enabled="true">
      <stringProp name="TestPlan.comments"></stringProp>
      <boolProp name="TestPlan.functional_mode">false</boolProp>
      <boolProp name="TestPlan.tearDown_on_shutdown">true</boolProp>
      <boolProp name="TestPlan.serialize_threadgroups">false</boolProp>
      <elementProp name="TestPlan.user_defined_variables" elementType="Arguments" guiclass="ArgumentsPanel" testclass="Arguments" testname="User Defined Variables" enabled="true">
        <collectionProp name="Arguments.arguments"/>
      </elementProp>
      <stringProp name="TestPlan.user_define_classpath"></stringProp>
    </TestPlan>
    <hashTree>'''

    # 각 API 엔드포인트에 대한 쓰레드 그룹 설정
    for endpoint, method in API_ENDPOINTS.items():
        headers = ENDPOINT_HEADERS.get(endpoint, ENDPOINT_HEADERS['default'])
        body = REQUEST_BODIES.get(endpoint, "")
        
        jmx_template += f''' #각 엔드포인트에 대한 쓰레드 그룹 어떻게 설정할 지?
      <ThreadGroup guiclass="ThreadGroupGui" testclass="ThreadGroup" testname="{endpoint} Test" enabled="true">
        <stringProp name="ThreadGroup.on_sample_error">continue</stringProp>
        <elementProp name="ThreadGroup.main_controller" elementType="LoopController" guiclass="LoopControlPanel" testclass="LoopController" testname="Loop Controller" enabled="true">
          <boolProp name="LoopController.continue_forever">false</boolProp>
          <stringProp name="LoopController.loops">1</stringProp>
        </elementProp>
        <stringProp name="ThreadGroup.num_threads">{thread_count}</stringProp>
        <stringProp name="ThreadGroup.ramp_time">1</stringProp>
        <boolProp name="ThreadGroup.scheduler">true</boolProp>
        <stringProp name="ThreadGroup.duration">{duration}</stringProp>
        <stringProp name="ThreadGroup.delay"></stringProp>
        <boolProp name="ThreadGroup.same_user_on_next_iteration">true</boolProp>
      </ThreadGroup>
      <hashTree>
        <HTTPSamplerProxy guiclass="HttpTestSampleGui" testclass="HTTPSamplerProxy" testname="{endpoint}" enabled="true">
          <boolProp name="HTTPSampler.postBodyRaw">true</boolProp>
          <elementProp name="HTTPsampler.Arguments" elementType="Arguments">
            <collectionProp name="Arguments.arguments">'''

        if method == "POST" and body:
            jmx_template += f'''
              <elementProp name="" elementType="HTTPArgument">
                <boolProp name="HTTPArgument.always_encode">false</boolProp>
                <stringProp name="Argument.value">{body}</stringProp>
                <stringProp name="Argument.metadata">=</stringProp>
              </elementProp>'''

        jmx_template += f'''
            </collectionProp>
          </elementProp>
          <stringProp name="HTTPSampler.domain">{config['server_name']}</stringProp>
          <stringProp name="HTTPSampler.port">{config['port']}</stringProp>
          <stringProp name="HTTPSampler.protocol">{config['protocol']}</stringProp>
          <stringProp name="HTTPSampler.contentEncoding">UTF-8</stringProp>
          <stringProp name="HTTPSampler.path">{endpoint}</stringProp>
          <stringProp name="HTTPSampler.method">{method}</stringProp>
          <boolProp name="HTTPSampler.follow_redirects">true</boolProp>
          <boolProp name="HTTPSampler.auto_redirects">false</boolProp>
          <boolProp name="HTTPSampler.use_keepalive">true</boolProp>
          <boolProp name="HTTPSampler.DO_MULTIPART_POST">false</boolProp>
          <stringProp name="HTTPSampler.embedded_url_re"></stringProp>
          <stringProp name="HTTPSampler.connect_timeout"></stringProp>
          <stringProp name="HTTPSampler.response_timeout"></stringProp>
        </HTTPSamplerProxy>
        <hashTree>
          <HeaderManager guiclass="HeaderPanel" testclass="HeaderManager" testname="HTTP Header Manager" enabled="true">
            <collectionProp name="HeaderManager.headers">'''

        for header_name, header_value in headers.items():
            jmx_template += f'''
              <elementProp name="" elementType="Header">
                <stringProp name="Header.name">{header_name}</stringProp>
                <stringProp name="Header.value">{header_value}</stringProp>
              </elementProp>'''

        jmx_template += '''
            </collectionProp>
          </HeaderManager>
          <hashTree/>
        </hashTree>
      </hashTree>'''

    # 결과 수집기 추가
    jmx_template += '''
      <ResultCollector guiclass="ViewResultsFullVisualizer" testclass="ResultCollector" testname="View Results Tree" enabled="true">
        <boolProp name="ResultCollector.error_logging">false</boolProp>
        <objProp>
          <name>saveConfig</name>
          <value class="SampleSaveConfiguration">
            <time>true</time>
            <latency>true</latency>
            <timestamp>true</timestamp>
            <success>true</success>
            <label>true</label>
            <code>true</code>
            <message>true</message>
            <threadName>true</threadName>
            <dataType>true</dataType>
            <encoding>false</encoding>
            <assertions>true</assertions>
            <subresults>true</subresults>
            <responseData>false</responseData>
            <samplerData>false</samplerData>
            <xml>false</xml>
            <fieldNames>true</fieldNames>
            <responseHeaders>false</responseHeaders>
            <requestHeaders>false</requestHeaders>
            <responseDataOnError>false</responseDataOnError>
            <saveAssertionResultsFailureMessage>true</saveAssertionResultsFailureMessage>
            <assertionsResultsToSave>0</assertionsResultsToSave>
            <bytes>true</bytes>
            <sentBytes>true</sentBytes>
            <url>true</url>
            <threadCounts>true</threadCounts>
            <idleTime>true</idleTime>
            <connectTime>true</connectTime>
          </value>
        </objProp>
        <stringProp name="filename"></stringProp>
      </ResultCollector>
      <hashTree/>
    </hashTree>
  </hashTree>
</jmeterTestPlan>'''

    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(jmx_template)
    
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(jmx_template)

    return full_path
    

def analyze_results(jtl_file: str, results_dir: str) -> Dict:
    """
    테스트 결과 분석 및 저장
    :param jtl_file: JMeter 결과 파일 (.jtl)
    :param results_dir: 결과 저장 디렉토리
    :return: 분석된 통계 정보
    """
    print(f"📊 테스트 결과 분석 중... ({jtl_file})")
    
    # JTL 파일 읽기
    df = pd.read_csv(jtl_file)
    
    # 기본 통계 계산
    stats = {
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "total_requests": len(df),
        "error_count": (df['success'] == False).sum(),
        "error_rate": float((df['success'] == False).mean() * 100),
        
        # 응답 시간 통계 (밀리초)
        "response_time": {
            "min": float(df['elapsed'].min()),
            "max": float(df['elapsed'].max()),
            "mean": float(df['elapsed'].mean()),
            "median": float(df['elapsed'].median()),
            "90th_percentile": float(df['elapsed'].quantile(0.90)),
            "95th_percentile": float(df['elapsed'].quantile(0.95)),
            "99th_percentile": float(df['elapsed'].quantile(0.99))
        },
        
        # 처리량 통계
        "throughput": {
            "requests_per_second": float(len(df) / (df['timeStamp'].max() - df['timeStamp'].min()) * 1000),
            "total_bytes": int(df['bytes'].sum()),
            "avg_bytes_per_request": float(df['bytes'].mean())
        },
        
        # 에러 상세 정보
        "errors": df[df['success'] == False]['responseMessage'].value_counts().to_dict(),
        
        # HTTP 응답 코드 분포
        "response_codes": df['responseCode'].value_counts().to_dict()
    }
    
    # 엔드포인트별 통계
    endpoint_stats = {}
    for endpoint in df['label'].unique():
        endpoint_df = df[df['label'] == endpoint]
        endpoint_stats[endpoint] = {
            "total_requests": len(endpoint_df),
            "error_rate": float((endpoint_df['success'] == False).mean() * 100),
            "avg_response_time": float(endpoint_df['elapsed'].mean()),
            "90th_percentile": float(endpoint_df['elapsed'].quantile(0.90)),
            "error_count": int((endpoint_df['success'] == False).sum())
        }
    
    stats["endpoint_statistics"] = endpoint_stats
    
    # JSON 파일로 저장
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    json_results_file = os.path.join(results_dir, f"test_results_{timestamp}.json")
    
    # 이렇게 사용:
    with open(json_results_file, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=4, ensure_ascii=False, cls=NumpyEncoder)
    
    print(f"✅ 분석 결과 저장 완료: {json_results_file}")
    
    # 요약 로그 파일 생성
    summary_file = os.path.join(results_dir, f"test_summary_{timestamp}.txt")
    with open(summary_file, 'w', encoding='utf-8') as f:
        f.write(f"스트레스 테스트 결과 요약\n")
        f.write(f"테스트 시간: {stats['timestamp']}\n")
        f.write(f"총 요청 수: {stats['total_requests']}\n")
        f.write(f"오류율: {stats['error_rate']:.2f}%\n")
        f.write(f"평균 응답 시간: {stats['response_time']['mean']:.2f}ms\n")
        f.write(f"90th 백분위 응답 시간: {stats['response_time']['90th_percentile']:.2f}ms\n")
        f.write(f"초당 요청 수: {stats['throughput']['requests_per_second']:.2f}\n")
        
        f.write("\n엔드포인트별 통계:\n")
        for endpoint, endpoint_stat in stats["endpoint_statistics"].items():
            f.write(f"\n{endpoint}:\n")
            f.write(f"  총 요청 수: {endpoint_stat['total_requests']}\n")
            f.write(f"  오류율: {endpoint_stat['error_rate']:.2f}%\n")
            f.write(f"  평균 응답 시간: {endpoint_stat['avg_response_time']:.2f}ms\n")
    
    print(f"📝 테스트 요약 저장 완료: {summary_file}")
    
    return stats

def run_stress_test(config: Dict):
    """
    스트레스 테스트 실행 메인 함수
    """
    base_results_dir = f"stress_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    os.makedirs(base_results_dir, exist_ok=True)
    
    # 스트레스 테스트 컨트롤러 초기화
    controller = StressTestController(config)
    
    # 테스트 설정 기록
    with open(os.path.join(base_results_dir, "test_config.json"), 'w') as f:
        json.dump(config, f, indent=4)
    
    while True:
        phase_dir = os.path.join(base_results_dir, 
                               f"phase_threads_{controller.current_threads}_duration_{controller.current_duration}")
        os.makedirs(phase_dir, exist_ok=True)
        
        print(f"\n🔄 테스트 단계 시작:")
        print(f"   - 쓰레드 수: {controller.current_threads}")
        print(f"   - 테스트 지속시간: {controller.current_duration}초")
        
        # JMeter 테스트 생성 및 실행
        jmx_file = create_jmx_file(config['server_config'], phase_dir, 
                                  controller.current_threads, controller.current_duration)
        success, result_file = run_jmeter_test(jmx_file, phase_dir)
        
        if not success:
            print("❌ 테스트 실행 실패")
            controller.failure_detected = True
            controller.failure_reason = "JMeter 실행 실패"
            break
            
        # 결과 분석
        stats = analyze_results(result_file, phase_dir)
        
        # 단계별 결과 출력
        print(f"\n📊 단계별 결과:")
        print(f"쓰레드 수: {controller.current_threads}")
        print(f"테스트 지속시간: {controller.current_duration}초")
        print(f"초당 요청 수: {stats['throughput']['requests_per_second']:.2f}")
        print(f"평균 응답 시간: {stats['response_time']['mean']:.2f}ms")
        print(f"오류율: {stats['error_rate']:.2f}%")
        print(f"90퍼센타일 응답 시간: {stats['response_time']['90th_percentile']:.2f}ms")
        
        # 계속 진행 여부 확인
        # 계속 진행 여부 확인
        adjusted_stats = {
            "error_rate": stats["error_rate"],
            "avg_response_time": stats["response_time"]["mean"]
        }
        should_continue, reason = controller.should_continue(adjusted_stats)
        
        if not should_continue:
            print(f"\n🛑 스트레스 테스트 완료: {reason}")
            controller.failure_detected = True
            controller.failure_reason = reason
            break
            
        # 다음 단계를 위한 파라미터 조정
        threshold_exceeded = (reason == "threshold_exceeded")
        result = controller.increment_test_parameters(threshold_exceeded)
        
        if result == "threads_increased":
            print(f"\n🔄 쓰레드 수 증가: {controller.current_threads}")
            print(f"   지속시간 초기화: {controller.current_duration}초")
        else:
            print(f"\n⏱️ 지속시간 증가: {controller.current_duration}초")
        
        # 단계 간 일시 중지
        time.sleep(5)

if __name__ == "__main__":
    print("🚀 JMeter 스트레스 테스트 시작")
    config = load_config()  # JSON 파일에서 설정 로드
    run_stress_test(config)