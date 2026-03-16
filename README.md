# LAH Terrain Path Planning Studio

**지형 기반 3차원 희소 waypoint 경로계획 연구 플랫폼**

GeoTIFF 지형 데이터를 사용하여 저고도 지형기반 임무 경로계획을 연구하는 로컬 HTML 기반 연구 플랫폼입니다.

## 주요 기능

- **지형 분석** — GeoTIFF 전처리, slope/roughness/curvature 등 10종 파생맵 생성
- **위험맵 구축** — 고도대별 위험원, LoS(Line of Sight) 계산, fused risk map
- **미션 설계** — 출발/목적지/관측박스/대기지점 설정, 미션 상태머신
- **환경 시뮬레이션** — Gymnasium 기반 2.5D 환경, K=32 후보 waypoint 선택
- **강화학습** — MaskablePPO 기반 학습, CUDA 지원, curriculum learning
- **평가/비교** — cross-terrain 평가, baseline 비교 (A*, FSM, Random)
- **시뮬레이션 재생** — top-down 경로 재생, 고도 프로파일, 이벤트 타임라인
- **실험 관리** — run_id 기반 실험 추적, config snapshot, 비교 리포트

## 기술 스택

| 구분 | 기술 |
|------|------|
| Frontend | React + TypeScript + Vite + Tailwind CSS |
| Backend | FastAPI + Pydantic v2 + Uvicorn |
| Engine | Python (numpy, scipy, rasterio, pyproj, shapely) |
| RL | Gymnasium + Stable Baselines3 + sb3-contrib |
| DL | PyTorch (CUDA 지원) |
| Charts | Plotly |
| DB | SQLite |
| State | Zustand + React Query |

## 설치

### 사전 요구사항

- Python 3.11+
- Node.js 20+
- CUDA 지원 PyTorch (선택사항, CPU에서도 동작)

### 1. 저장소 클론

```bash
git clone https://github.com/HyeonJun9138/LAHPathPlanningStudio.git
cd LAHPathPlanningStudio
```

### 2. GeoTIFF 배치

`resource/` 폴더에 세 개의 tif 파일을 배치합니다:

```
resource/
├── Hongik_48km.tif
├── Inje_48km.tif
└── Jipo_48km.tif
```

### 3. Python 환경 설정

```bash
# venv 사용
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Linux/Mac

# 패키지 설치
pip install -r apps/backend/requirements.txt
```

### 4. CUDA 확인

```bash
python scripts/check_cuda.py
```

### 5. 프론트엔드 설치

```bash
cd apps/frontend
npm install
cd ../..
```

## 실행

### 백엔드 실행

```bash
cd apps/backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 프론트엔드 실행

```bash
cd apps/frontend
npm run dev
```

### Windows PowerShell (한 번에 실행)

```powershell
.\scripts\run_all.ps1
```

브라우저에서 http://localhost:5173 접속

## 프로젝트 구조

```
LAHPathPlanningStudio/
├── resource/           # GeoTIFF, 위험원, 미션 프리셋
├── apps/
│   ├── backend/        # FastAPI 서버 (36개 API)
│   └── frontend/       # React GUI (12탭)
├── src/engine/         # Python 연구 엔진
│   ├── io/             # GeoTIFF 로더
│   ├── terrain/        # 지형 전처리, 파생맵, 패치 추출
│   ├── hazard/         # 위험원, LoS, 위험맵
│   ├── mission/        # 미션, 프리미티브, 후보 생성
│   ├── env/            # Gymnasium 환경
│   ├── training/       # SB3 학습 파이프라인
│   ├── evaluation/     # 평가, 비교
│   ├── simulation/     # 롤아웃, 재생 데이터
│   ├── baselines/      # 비교 baseline (A*, FSM, Random)
│   └── reporting/      # DB, 리포트 생성
├── configs/            # YAML 설정 파일
├── scripts/            # 실행/설치 스크립트
├── workspace/          # 프로젝트별 작업 공간
├── tests/              # 단위/통합 테스트
└── docs/               # 아키텍처 문서
```

## GUI 탭 구성 (12탭)

1. **Dashboard** — 프로젝트 개요, CUDA 상태, 최근 실행
2. **Resource Manager** — GeoTIFF 등록, 메타데이터 확인
3. **Terrain Analysis** — 지형 전처리, 파생맵 시각화
4. **Hazard & LoS Builder** — 위험원/제한구역, 위험맵 빌드
5. **Mission Designer** — 임무 요소 배치, JSON 편집
6. **Candidate & Primitive Lab** — 후보 waypoint, dry-run
7. **Training Center** — 학습 설정, 실시간 커브
8. **Evaluation** — 성능 평가, baseline 비교
9. **Simulation Player** — 경로 재생, 고도 프로파일
10. **Experiment Compare** — 다중 실험 비교
11. **Reports** — Markdown/HTML 리포트 생성
12. **Settings** — 환경 설정

## 연구 범위

이 플랫폼은 아래의 **안전한 연구 범위**를 다룹니다:

- 목적지까지 지형 기반 안전 이동
- 위험 지역/제한구역 회피
- 저고도 안전 대기
- 관측 박스 접근 및 LoS 확보 (pop-up observe)
- 관측 후 drop-down 및 안전 이탈
- 복귀 또는 대체 착륙 지점 전환

산악 지형 비행, 재난 대응, 감시 관측, 점검 임무, 민수형 항공 경로 생성에 활용 가능합니다.

## 핵심 설계 원칙

- **2.5D terrain + altitude band** (full 3D voxel이 아님)
- **Sparse waypoint planning** — 정책은 K=32 후보 중 선택
- **Motion primitive executor** — 실제 비행 궤적 생성
- **Action masking** — 불가능한 선택 자동 제거
- **재현성** — 모든 실행에 run_id, config snapshot, seed 기록

## 설정 파일

- `configs/app.yaml` — 앱 전역 설정
- `configs/preprocess_config.yaml` — 지형 전처리 기본 설정
- `resource/hazards/sample_hazards.json` — 예시 위험원
- `resource/missions/sample_mission.yaml` — 예시 미션
- `resource/presets/reward_default.yaml` — 보상 가중치
- `resource/presets/candidate_default.yaml` — 후보 생성 설정
- `resource/presets/curriculum_*.yaml` — 커리큘럼 프리셋

## 흔한 오류 해결

| 오류 | 해결 |
|------|------|
| `rasterio` 설치 실패 | `pip install rasterio` 대신 conda: `conda install -c conda-forge rasterio` |
| CUDA not found | PyTorch CUDA 버전 설치: `pip install torch --index-url https://download.pytorch.org/whl/cu121` |
| Port 8000 사용 중 | `uvicorn app.main:app --port 8001` |
| 긴 경로 에러 (Windows) | `git config --global core.longpaths true` |
| npm install 오류 | Node.js 20+ 확인, `npm cache clean --force` 후 재설치 |

## 라이선스

연구 목적으로 제작되었습니다.
