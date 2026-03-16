# LAH Terrain Path Planning Studio — Architecture

## 시스템 아키텍처 개요

```
┌─────────────────────────────────────────────────────────┐
│                    React Frontend (12 Tabs)               │
│         TypeScript + Vite + Tailwind + Plotly             │
│         http://localhost:5173                              │
└──────────────────┬────────────────────────────────────────┘
                   │ REST API + WebSocket (Job Events)
                   ▼
┌─────────────────────────────────────────────────────────┐
│                    FastAPI Backend                         │
│         36 API endpoints + Job Manager                    │
│         http://localhost:8000                              │
├─────────────────────────────────────────────────────────┤
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │
│  │ Projects │ │ Terrain  │ │ Hazard   │ │ Mission  │   │
│  │ API      │ │ API      │ │ API      │ │ API      │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │
│  │ Training │ │ Eval     │ │ Sim      │ │ Reports  │   │
│  │ API      │ │ API      │ │ API      │ │ API      │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘   │
├─────────────────────────────────────────────────────────┤
│         Core: Config / Database / Job Manager             │
└──────────────────┬────────────────────────────────────────┘
                   │ Python calls
                   ▼
┌─────────────────────────────────────────────────────────┐
│                    Python Engine (src/engine/)             │
├────────┬────────┬────────┬────────┬────────┬────────────┤
│Terrain │Hazard  │Mission │ Env    │Training│ Evaluation  │
│Pipeline│Pipeline│Schema  │Gym Env │SB3     │ Evaluator   │
│        │        │FSM     │Reward  │PPO     │ Compare     │
│Derive  │LoS     │Primit. │Obs     │Featur. │ Simulation  │
│Patch   │Risk    │Candid. │        │Callbk. │ Baselines   │
│Cache   │Fusion  │        │        │        │ Reports     │
└────────┴────────┴────────┴────────┴────────┴────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│            Storage Layer                                   │
│  ┌──────────┐  ┌──────────────┐  ┌────────────────┐     │
│  │ SQLite   │  │ workspace/   │  │ resource/      │     │
│  │ (runs,   │  │ projects/    │  │ GeoTIFF files  │     │
│  │  metrics │  │ (run dirs,   │  │ hazards.json   │     │
│  │  tags)   │  │  checkpoints │  │ missions.yaml  │     │
│  │          │  │  plots, logs │  │ presets/        │     │
│  └──────────┘  └──────────────┘  └────────────────┘     │
└─────────────────────────────────────────────────────────┘
```

## 엔진 파이프라인 흐름

```
GeoTIFF → [Terrain Pipeline] → DEM + 파생맵 + 캐시
     ↓
위험원 JSON → [Hazard Pipeline] → altitude band별 risk map + LoS map
     ↓
미션 YAML → [Mission Schema] → state machine + primitives
     ↓
[Candidate Generator] → K=32 후보 waypoint + features + action mask
     ↓
[Gymnasium Env] → observation Dict + reward + done
     ↓
[MaskablePPO Training] → checkpoint + metrics + curves
     ↓
[Evaluator] → cross-terrain eval + baseline compare
     ↓
[Simulation Player] → episode replay + export
     ↓
[Report Generator] → markdown/HTML report
```

## Gymnasium 환경 설계

### Observation Space (Dict)
| Key | Shape | Description |
|-----|-------|-------------|
| self_state | (48,) | 위치, 속도, 고도, 모드, 연료, 시간 등 |
| local_hi_patch | (C, 32, 32) | 고해상도 지형 패치 |
| local_mid_patch | (C, 16, 16) | 중해상도 지형 패치 |
| global_context | (16,) | 전역 임무 진행도 |
| candidate_table | (32, 24) | K개 후보 feature 테이블 |
| action_mask | (32,) | 유효 후보 마스크 |

### Action Space
- Discrete(32): 32개 후보 waypoint 중 하나 선택

### Reward 구성
- goal_progress (+)
- mission_complete_bonus (+)
- observation_complete (+)
- integrated_risk (-)
- visible_time (-)
- altitude_violation (-)
- zone_violation (-)
- collision (-)

## 데이터 흐름

### Run 산출물 구조
```
workspace/projects/{project}/runs/{stage}/{run_id}/
├── configs/      # YAML config snapshot
├── metrics/      # CSV + JSON metrics
├── plots/        # PNG charts
├── artifacts/    # numpy arrays, models, exports
├── logs/         # console.log
└── meta/         # run_meta.json, environment.json
```

### Run ID 형식
`{stage}__{terrain}__{scenario}__{timestamp}__{shortid}`

예: `04_training__Hongik_48km__curriculumB__20260314_231500__a1b2c3`
