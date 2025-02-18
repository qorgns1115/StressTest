import subprocess
import json
import time
import pandas as pd
import schedule
import os
from datetime import datetime
import requests
from typing import Dict, Tuple, Optional

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
# asdasdfasdfdsaf
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
    result_file = os.path.join(results_dir, "test_results.jtl") #결과 저장 디렉토리랑 jtl 파일 연결
    log_file = os.path.join(results_dir, "jmeter.log")
    
    print(f"🚀 JMeter 테스트 실행 중...")
    print(f"📁 결과 디렉토리: {results_dir}")
    
    cmd = f'"{JMETER_PATH}" -n -t "{jmx_file}" -l "{result_file}" -j "{log_file}"' #jmeter 실행 파일 경로, gui 없이, test plan, log file 경로, jmeter log file 경로 지정
    
    try:
        # JMeter 실행 및 실시간 출력 캡처
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) #실행된 프로세스가 끝날 때까지 기다리지 않는 비동기 실행 방식
        #표준출력을 파이프로 연결 > 프로세스의 출력을 파이썬 코드에서 읽을 수 있음, 표준에러를 표준출력으로 리다이렉트함으로써 일반 출력과 에러 메시지가 모두 같은 파이프로 전달돼서 에러와 일반 출력을 함께 처리
        #입출력을 문자열로 처리하도록 지정
        
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None: #output이 공백이거나, poll이 not none(실행된 프로세스 종료)동시에 되면 루프 빠져나감
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

def get_user_input():
    """기본 서버 설정 정보 입력 받기"""
    print("📌 JMeter 자동화 테스트를 위한 기본 정보를 입력하세요.")
    protocol = input("Protocol (http/https): ").strip()
    server_name = input("Server Name or IP: ").strip()
    port = input("Port Number (예: 8080): ").strip()
    
    return {
        "protocol": protocol,
        "server_name": server_name,
        "port": port
    }

class StressTestController:
    def __init__(self, initial_threads=610, thread_increment=5, max_threads=1000,
                 error_threshold=5, response_time_threshold=5000):
        """
        스트레스 테스트 컨트롤러 초기화
        :param initial_threads: 초기 쓰레드 수 (기본값: 10)
        :param thread_increment: 단계별 쓰레드 증가량 (기본값: 10)
        :param max_threads: 최대 쓰레드 수 (기본값: 1000)
        :param error_threshold: 오류율 임계값(%) (기본값: 5%)
        :param response_time_threshold: 응답시간 임계값(ms) (기본값: 5000ms)
        """
        self.initial_threads = initial_threads
        self.thread_increment = thread_increment
        self.max_threads = max_threads
        self.error_threshold = error_threshold  # 허용 가능한 최대 오류율
        self.response_time_threshold = response_time_threshold  # 허용 가능한 최대 응답 시간
        self.current_threads = initial_threads
        self.test_phase = "running"
        self.failure_detected = False
        self.failure_reason = None
        
    def should_continue(self, stats: Dict) -> Tuple[bool, Optional[str]]:
        """
        테스트 지속 여부 결정
        :param stats: 현재 테스트 통계
        :return: (계속 진행 여부, 중단 사유)
        """
        if stats["error_rate"] > self.error_threshold:
            return False, f"오류율이 임계값을 초과함: {stats['error_rate']}%"
        
        if stats["avg_response_time"] > self.response_time_threshold:
            return False, f"응답 시간이 임계값을 초과함: {stats['avg_response_time']}ms"
            
        if self.current_threads >= self.max_threads:
            return False, f"최대 쓰레드 수에 도달함: {self.max_threads}"
            
        return True, None

    def increment_threads(self) -> int:
        """다음 테스트 단계를 위한 쓰레드 수 증가"""
        self.current_threads += self.thread_increment
        return self.current_threads

def create_jmx_file(config, results_dir, thread_count, filename="generated_test.jmx"):
    """
    JMeter 테스트 설정 파일 생성
    :param config: 서버 설정 정보
    :param results_dir: 결과 저장 디렉토리
    :param thread_count: 현재 쓰레드 수
    :param filename: 생성할 파일명
    """
    full_path = os.path.join(results_dir, filename)
    
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
        <stringProp name="ThreadGroup.duration">30</stringProp>
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
    테스트 결과 분석
    :param jtl_file: JMeter 결과 파일
    :param results_dir: 결과 저장 디렉토리
    :return: 분석된 통계 정보
    """
    df = pd.read_csv(jtl_file)
    
    # 데이터 타입 변환을 위한 함수
    def convert_to_serializable(value):
        if pd.api.types.is_integer_dtype(type(value)):
            return int(value)
        elif pd.api.types.is_float_dtype(type(value)):
            return float(value)
        return value
    
    stats = {
        "total_requests": int(len(df)),
        "error_rate": float((df['success'] == False).mean() * 100),
        "avg_response_time": float(df['elapsed'].mean()),
        "max_response_time": float(df['elapsed'].max()),
        "min_response_time": float(df['elapsed'].min()),
        "90th_percentile": float(df['elapsed'].quantile(0.90)),
        "95th_percentile": float(df['elapsed'].quantile(0.95)),
        "requests_per_second": float(len(df) / (df['timeStamp'].max() - df['timeStamp'].min()) * 1000),
        "error_count": int((df['success'] == False).sum())
    }
    
    # 모든 값을 기본 Python 타입으로 변환
    serializable_stats = {k: convert_to_serializable(v) for k, v in stats.items()}

    # 상세 통계 저장
    with open(os.path.join(results_dir, f"phase_stats_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"), 'w') as f:
        json.dump(serializable_stats, f, indent=4)
        
    return stats

def run_stress_test(config: Dict):
    """
    스트레스 테스트 실행 메인 함수
    :param config: 서버 설정 정보
    """
    base_results_dir = f"stress_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    os.makedirs(base_results_dir, exist_ok=True)
    
    # 스트레스 테스트 컨트롤러 초기화
    controller = StressTestController()
    
    # 테스트 설정 기록
    with open(os.path.join(base_results_dir, "test_config.json"), 'w') as f:
        json.dump({
            "initial_threads": controller.initial_threads,
            "thread_increment": controller.thread_increment,
            "max_threads": controller.max_threads,
            "error_threshold": controller.error_threshold,
            "response_time_threshold": controller.response_time_threshold,
            "server_config": config
        }, f, indent=4)
    
    while True:
        phase_dir = os.path.join(base_results_dir, f"phase_{controller.current_threads}_threads")
        os.makedirs(phase_dir, exist_ok=True)
        
        print(f"\n🔄 {controller.current_threads}개의 쓰레드로 테스트 단계 시작")
        
        # JMeter 테스트 생성 및 실행
        jmx_file = create_jmx_file(config, phase_dir, controller.current_threads)
        success, result_file = run_jmeter_test(jmx_file, phase_dir)
        
        if not success:
            print("❌ 테스트 실행 실패")
            controller.failure_detected = True
            controller.failure_reason = "JMeter 실행 실패"
            break
            
        # 결과 분석
        stats = analyze_results(result_file, phase_dir)
        
        # 단계별 결과 출력
        print(f"\n📊 단계별 결과 (쓰레드 수: {controller.current_threads})")
        print(f"초당 요청 수: {stats['requests_per_second']:.2f}")
        print(f"평균 응답 시간: {stats['avg_response_time']:.2f}ms")
        print(f"오류율: {stats['error_rate']:.2f}%")
        print(f"90퍼센타일 응답 시간: {stats['90th_percentile']:.2f}ms")
        
        # 계속 진행 여부 확인
        should_continue, reason = controller.should_continue(stats)
        if not should_continue:
            print(f"\n🛑 스트레스 테스트 중단: {reason}")
            controller.failure_detected = True
            controller.failure_reason = reason
            break
            
        # 다음 단계를 위한 쓰레드 수 증가
        controller.increment_threads()
        
        # 단계 간 일시 중지
        time.sleep(5)
    

if __name__ == "__main__":
    print("🚀 JMeter 스트레스 테스트 시작")
    config = get_user_input()
    run_stress_test(config)

#사용자 입력(프로토콜, 서버 주소, 포트 번호) > jmeter 테스트 설정 파일(jmx) 생성(api 엔드포인트와 요청 방식 설정, 쓰레드 수와 요청 body, header 설정, 요청을 반복할 지 여부 설정) > jmeter 테스트 실행해서 실시간 로그 출력(jmeter가 api 부하 테스트 수행 후 응답 데이터 기록) > 테스트 결과를 jtl 파일에 저장
# > 테스트 결과 분석(평균 응답 시간, 최대 응답 시간, 오류율, 초당 요청 수)후 json 파일로 저장, 이로 인해 api 성능 데이터 확보 > stresstestcontroller로 thread 수 증가시키면서 성능 테스트 함 > stress test 실행 및 반복, 이를 통해 api의 최대 처리 성능과 한계점 파악 > 보고서 생성


#get user input으로 사용자 입력 받고, jmeter 테스트 파일 jmx 파일 api 엔드포인트랑, http 요청방식, 헤더, 바디 이런거 설정해서 만들고 jmetertest 실행해서 jtl 파일 만들어서 로그 저장하고 stresstestcontroller 객체 생성해서 runstresstest해서 점진적으로 쓰레드수 늘려가면서 성능테스트 반복하고 jtl 파일 읽어서 api 응답시간, 오류율, 요청 수 등의 통계 분석, 
# 이후 should_continue() 함수로 임계값 초과 여부 판단해서 특정 조건 발생 시 중단
# 최대 쓰레드 620
 