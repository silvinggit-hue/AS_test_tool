

# AS Test Tool v4

> IP Camera(TTA Firmware) 제어를 위한 비표준 환경 대응 통합 테스트 도구

---

## Overview

AS Test Tool v4는
**불완전한 HTTP API를 사용하는 IP 카메라를 안정적으로 제어하기 위해 설계된 시스템**이다.

이 프로젝트는 단순한 API 클라이언트가 아니라:

* 비표준 응답 처리
* 인증 변형 대응 (Digest / Basic)
* 장비별 API 차이 흡수
* 네트워크 불안정성 대응

까지 포함한 **실무형 제어 플랫폼**이다.

---

## Why this project is difficult

일반적인 REST API 환경이 아니다.

### Non-standard API behavior

* 실패 응답인데 HTTP 200 반환
* 인증 실패가 body에 문자열로 포함됨
* endpoint가 존재하지만 동작하지 않는 경우 존재

---

### Device-dependent API structure

```text
/httpapi/
/webapi/
```

* 동일 기능이 서로 다른 경로에 존재
* 런타임에서 자동 판단 필요

---

### Unstable authentication

* Digest / Basic 혼용
* 일부 장비는 정상 challenge를 제공하지 않음
* 200 응답 + 인증 실패 메시지 케이스 존재

---

### ReadParam limitations

```text
ReadParam?action=readparam&KEY1=0&KEY2=0 ...
```

* multi-key 요청이 불안정
* 실패 시 원인 key 식별 불가

---

### Network instability

* RemoteDisconnected
* timeout
* 무응답 상태 (정상 동작 포함)

---

## Key solutions

### Robust success 판단

```python
if status == 200 and "error" not in body:
    success
```

→ HTTP status가 아닌 **실제 의미 기반 판단**

---

### ReadParam fallback strategy

```text
multi request
  ↓ 실패
chunk 분할
  ↓ 실패
single request
```

→ 어떤 장비에서도 반드시 동작하도록 설계

---

### Automatic API path fallback

```text
/httpapi/ → /webapi/
```

→ 404 발생 시 자동 전환

---

### Authentication recovery

* 401 → digest 재협상
* 200 + auth error → 실패 처리

---

### Task queue based control system

단순 요청 구조가 아니라:

```text
Queue + Priority + Polling + State control
```

---

## Architecture

```text
UI (PyQt)
  ↓
RequestHubWorker (Task Queue)
  ↓
CamApiClient (API abstraction)
  ↓
Device
```

---

## Core features

* Device Info / Status 조회
* ReadParam / WriteParam API 처리
* PTZ 제어 (state 기반)
* Firmware 업로드 자동화
* Audio / Video 설정 제어
* 실시간 상태 Polling

---

## Highlights

* Digest 인증 직접 구현
* 비표준 API 대응 로직 설계
* Task Queue 기반 제어 구조
* 다양한 장비 환경에서 안정성 확보

---

## What this project demonstrates

이 프로젝트는 다음 역량을 보여준다:

* 불완전한 시스템을 분석하고 구조화하는 능력
* 예외 상황을 고려한 설계
* 네트워크 / 인증 / 상태 관리 통합 처리
* 실무 환경에서의 안정성 확보

---

## One-line summary

```text
A control system designed to operate reliably on non-standard and unstable device APIs.
```

---

## Future improvements

* Device profile-based behavior optimization
* API normalization layer
* Extended automation scenarios

---

## Final note

이 프로젝트의 핵심은 단순한 기능 구현이 아니라:

> **“정상적이지 않은 환경을 제어 가능한 시스템으로 만든 것”**

이다.

---
