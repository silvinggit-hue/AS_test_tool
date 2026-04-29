# 📘 AS Test Tool v4 README

## 1. 개요

AS Test Tool v4는 IP 카메라 장비의 상태 조회, 설정 변경, PTZ 제어, 펌웨어 업로드 등을
HTTP API 기반으로 자동화하는 도구이다.

핵심 특징:

* ReadParam / WriteParam / GetState API 통합 처리
* Digest / Basic 인증 자동 대응
* 장비 상태 실시간 Polling
* PTZ 제어 및 영상/오디오 설정 지원
* 펌웨어 업로드 자동화
* 네트워크 및 인증 예외 처리 내장

---

## 2. 아키텍처

```text
UI (PyQt)
  ↓
Worker Layer
  ↓
Core Layer (API 처리)
  ↓
Device (IP Camera)
```

---

## 3. 핵심 구성

### 3.1 Core Layer

#### 📄 CamApiClient

* 모든 HTTP API 요청의 중심
* 인증 처리 (Digest / Basic)
* ReadParam / WriteParam / GetState 제공

주요 기능:

* `_request()` : 공통 요청 처리
* `read_param_text()` : 단일 key 조회
* `read_params_text()` : multi key 조회
* `write_param_raw()` : 설정 변경
* `get_state_text()` : 상태 조회

👉 인증 실패를 body까지 검사하는 구조 포함됨

---

#### 📄 CamInfoReader 

장비 기본 정보 조회 모듈

```python
data = CamInfoReader(client).get_info_block()
```

수집 정보:

* 모델명 (SYS_MODELNAME)
* 펌웨어 (SYS_VERSION)
* 보드 ID
* MAC
* 디스크 상태
* 모듈 정보

특징:

* FAST_KEYS / SLOW_KEYS 분리
* 멀티 요청 실패 시 자동 fallback 분할 요청
* 최종적으로 단일 요청까지 내려가는 구조

---

#### 📄 CamStatusReader

실시간 상태 조회

수집 정보:

* 온도
* CDS / Current
* RTC 시간
* 팬 상태
* 네트워크 상태
* 비트레이트 / FPS

---

#### 📄 http_client

* urllib 기반 요청
* SSL 호환성 처리 (구형 장비 대응)
* timeout / retry 처리

---

#### 📄 firmware_upload

* progress.html 업로드 방식 사용
* Digest 인증 대응
* 업로드 후 연결 끊김 → reboot로 판단

---

### 3.2 Worker Layer

#### 📄 RequestHubWorker 

전체 제어의 중심

역할:

* 모든 API 요청 큐 처리
* Polling 관리
* PTZ 제어
* Read/WriteParam 실행
* 펌웨어 업로드
* 오디오/비디오 설정

핵심 구조:

```text
Queue 기반 Task 처리
 + Priority 관리
 + Polling loop
 + PTZ hold 상태 유지
```

주요 기능:

* PTZ 제어
* ReadParam / WriteParam
* 상태 Polling
* Firmware Upload
* Audio 설정
* Video 입력 설정

---

#### 📄 DeviceInfoWorker

* 여러 비밀번호 후보로 로그인 시도
* 성공 시 장비 정보 반환

---

#### 📄 Phase1Worker

* 장비 접속 초기 단계
* 인증 방식 판단
* root_path 자동 탐색

---

## 4. API 구조

모든 요청은 기본적으로 다음 형태:

```
/httpapi/ReadParam?action=readparam&KEY=0
/httpapi/WriteParam?action=writeparam&KEY=VALUE
/httpapi/GetState?action=...
```

---

## 5. 주요 기능

### 5.1 상태 조회

```python
reader = CamStatusReader(client)
status = reader.read_status_block()
```

---

### 5.2 장비 정보 조회

```python
info = CamInfoReader(client).get_info_block()
```

---

### 5.3 파라미터 읽기

```python
value = client.read_param_value("SYS_VERSION")
```

---

### 5.4 파라미터 쓰기

```python
client.write_param_raw({
    "VID_RESOLUTION": "1080p"
})
```

---

### 5.5 PTZ 제어

```python
SendPTZ?action=sendptz&PTZ_MOVE=up,5,1
```

---

### 5.6 펌웨어 업로드

```python
upload_firmware_progress_html(...)
```

---

## 6. 예외 처리 전략

### 네트워크

* timeout → retry
* RemoteDisconnected → 재시도 후 실패 처리

### 인증

* 401 → Digest challenge 재요청
* 200 + auth error → 실패 처리

### 장비 특이 케이스

* 일부 장비는 인증 실패 시 200 반환
* multi ReadParam 실패 → 분할 요청

---

## 7. 주의사항

### ❗ 오판 방지

* 동일한 오류 메시지라도 원인이 다를 수 있음
* 반드시 로그 기반으로 판단
* 추정으로 조치 금지

---

### ❗ 네트워크 우선 확인

* 접속 실패 ≠ 장비 불량
* Ping / 포트 / IP 먼저 확인

---

### ❗ 인증 관련

* 비밀번호 반복 입력 금지 (계정 잠금 가능)

---

### ❗ 작업 정책

* 무조건적인 재부팅 금지
* 초기화 전 고객 동의 필수
* 점검 순서 준수

---

### ❗ 핵심 원칙

```
모든 판단은 로그 기반으로 진행
```

---

## 8. 개발 시 주의사항

### 1. root_path 처리

* `/httpapi/` vs `/webapi/` 혼용 장비 존재

---

### 2. 인증 방식

* Digest → 기본
* Basic → 일부 구형 장비

---

### 3. ReadParam

* multi 요청 실패 가능성 있음
  → 반드시 fallback 구조 유지

---

### 4. 펌웨어 업로드

* 업로드 후 connection 종료 정상 동작

---

## 9. 향후 개선 방향

* API 응답 구조 표준화
* 로그 레벨 세분화
* 장비별 프로파일링
* UI 상태 표시 개선

---

## 결론

이 시스템은 단순 API 호출 도구가 아니라
👉 **장비 상태 판단 + 제어 + 자동화 통합 플랫폼**

---
