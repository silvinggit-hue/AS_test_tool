# AS_test_tool

PyQt5 기반 IP 카메라 테스트 및 장비 제어 도구

## 개요
이 프로젝트는 IP 카메라 장비에 대해 연결, 장비 정보 조회, 상태 조회, PTZ 제어, 오디오 테스트, 비디오 입력 포맷 제어, 펌웨어 업로드 등의 기능을 제공하는 테스트 툴입니다.

## 주요 기능
- 장비 연결 / 연결 해제
- Phase1 연결 및 인증 처리
- 장비 정보 조회
- 상태 조회 및 주기 polling
- PTZ / Zoom / Focus / TDN / ICR 제어
- Audio 테스트
- Video Input Format 제어
- Firmware 업로드
- Camera Log 조회

## 프로젝트 구조
- `config/` : 기본 설정
- `controller/` : 연결 유스케이스
- `core/` : HTTP, Digest, Probe, API Client, Info/Status Reader
- `models/` : DTO 및 공통 예외 타입
- `data/` : 보드별 입력 포맷 정적 데이터
- `ui/` : PyQt5 기반 메인 UI
- `ui/widgets/` : 조이스틱 등 커스텀 위젯
- `workers/` : 비동기 worker 계층
- `utils/` : 로깅 설정 등 보조 유틸

## 실행 환경
- Python 3.10+
- PyQt5
- requests

## 설치
```bash
pip install -r requirements.txt