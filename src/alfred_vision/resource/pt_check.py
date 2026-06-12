import torch

# 🌟 weights_only=False를 주면 복잡한 클래스 구조도 에러 없이 한방에 로드됩니다.
ckpt = torch.load(
    '/home/rokey/alfred_ws/src/alfred_vision/resource/best.pt', 
    map_location='cpu', 
    weights_only=False
)

print("🎉 [성공] .pt 파일 로드 완료!")
print("\n1. 상위 데이터 키 목록:")
print(ckpt.keys())

# YOLO 모델 구조가 저장되어 있다면 가볍게 확인
if 'model' in ckpt:
    print("\n2. 모델 구조 (일부 출력):")
    print(str(ckpt['model'])[:1000]) # 너무 길 수 있으니 앞부분 1000자만 출력