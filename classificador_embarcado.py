import argparse
import os
import sys
import threading
import time
from collections import Counter, deque

os.environ.setdefault("QT_QPA_PLATFORM", "xcb")
os.environ.setdefault("QT_QPA_FONTDIR", "/usr/share/fonts/truetype/dejavu")

import cv2
from ultralytics import YOLO

MODELO_PADRAO = "best.pt"        # seu V3 (yolov8l-cls) baixado do Drive
PORTA_PADRAO = "/dev/ttyACM0"    # confira com: ls /dev/ttyACM* /dev/ttyUSB*
BAUD = 9600                      # tem que ser igual ao do sketch .ino

CONF_MIN = 0.70                  # threshold de confianca
JANELA = 8                       # frames na janela temporal
MIN_VOTOS = 6                    # votos iguais para confirmar a decisao
COOLDOWN = 3.0                   # segundos travados apos acionar o servo
ROI_FRACAO = 0.55                # fracao central do frame enviada ao modelo
IMGSZ = 224                      # mesmo tamanho usado no treino

GRUPOS = {
    "C1": ("V", "IMATURA",  (0, 200, 0)),
    "C2": ("V", "IMATURA",  (0, 200, 0)),
    "C3": ("M", "MADURA",   (0, 200, 220)),
    "C4": ("M", "MADURA",   (0, 200, 220)),
    "C5": ("M", "MADURA",   (0, 200, 220)),
    "C6": ("R", "PODRE",    (0, 0, 230)),
}


def abrir_serial(porta):
    import serial  
    ser = serial.Serial(porta, BAUD, timeout=1)
    time.sleep(2.0) 
    ser.reset_input_buffer()
    return ser


def recortar_roi(frame, fracao):
    h, w = frame.shape[:2]
    lado = int(min(h, w) * fracao)
    x0 = (w - lado) // 2
    y0 = (h - lado) // 2
    return frame[y0:y0 + lado, x0:x0 + lado], (x0, y0, lado)


class LeitorCamera:
    def __init__(self, fonte):
        self.cap = cv2.VideoCapture(fonte)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.ok = self.cap.isOpened()
        self.frame = None
        self.lock = threading.Lock()
        self.rodando = self.ok
        if self.ok:
            threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while self.rodando:
            ok, frame = self.cap.read()
            if ok:
                with self.lock:
                    self.frame = frame
            else:
                time.sleep(0.05)

    def ler(self):
        with self.lock:
            return None if self.frame is None else self.frame.copy()

    def parar(self):
        self.rodando = False
        time.sleep(0.1)
        self.cap.release()


def decisao_por_votacao(historico):
    """Retorna a classe com maioria na janela temporal, ou None."""
    validos = [c for c in historico if c is not None]
    if not validos:
        return None
    classe, votos = Counter(validos).most_common(1)[0]
    return classe if votos >= MIN_VOTOS else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelo", default=MODELO_PADRAO)
    ap.add_argument("--porta", default=PORTA_PADRAO)
    ap.add_argument("--cam", default="0",
                    help="indice da webcam (0, 1...) ou URL do DroidCam, "
                         "ex: http://192.168.0.15:4747/video")
    ap.add_argument("--sem-arduino", action="store_true",
                    help="roda so a visao computacional, sem abrir a serial")
    args = ap.parse_args()

    print(f"[..] carregando modelo: {args.modelo}")
    modelo = YOLO(args.modelo)
    print(f"[ok] classes do modelo: {modelo.names}")

    ser = None
    if not args.sem_arduino:
        try:
            ser = abrir_serial(args.porta)
            print(f"[ok] serial aberta em {args.porta}")
        except Exception as e:
            print(f"[!!] falha na serial ({e}). Rodando sem Arduino.")

    fonte = int(args.cam) if args.cam.isdigit() else args.cam
    print(f"[..] abrindo camera: {fonte}")
    cam = LeitorCamera(fonte)
    if not cam.ok:
        sys.exit(f"[!!] nao consegui abrir a camera {fonte}. "
                 "Se for DroidCam: app aberto, mesma rede Wi-Fi, IP correto?")

    historico = deque(maxlen=JANELA)
    ultimo_comando = None
    fim_cooldown = 0.0

    print("[ok] rodando. 'q' para sair.")
    try:
        while True:
            frame = cam.ler()
            if frame is None:      # stream ainda nao entregou o 1o frame
                time.sleep(0.05)
                continue

            roi, (x0, y0, lado) = recortar_roi(frame, ROI_FRACAO)
            r = modelo.predict(roi, imgsz=IMGSZ, verbose=False)[0]

            idx = int(r.probs.top1)
            conf = float(r.probs.top1conf)
            classe = modelo.names[idx]

            historico.append(classe if conf >= CONF_MIN else None)

            agora = time.time()
            confirmada = decisao_por_votacao(historico)

            if confirmada and agora >= fim_cooldown:
                comando, rotulo, _ = GRUPOS[confirmada]
                if comando != ultimo_comando:
                    if ser:
                        ser.write(comando.encode())
                    print(f"[->] {confirmada} ({rotulo}) conf={conf:.2f} cmd={comando}")
                    ultimo_comando = comando
                    fim_cooldown = agora + COOLDOWN

            # --- overlay ---
            cor = GRUPOS[classe][2] if classe in GRUPOS else (200, 200, 200)
            cv2.rectangle(frame, (x0, y0), (x0 + lado, y0 + lado), cor, 2)
            cv2.putText(frame, f"{classe} {conf:.2f}", (x0, y0 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, cor, 2)
            estado = f"CONFIRMADO: {confirmada}" if confirmada else "analisando..."
            if agora < fim_cooldown:
                estado += f"  [cooldown {fim_cooldown - agora:.1f}s]"
            cv2.putText(frame, estado, (12, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

            cv2.imshow("Classificador de laranjas C1-C6", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        if ser:
            ser.write(b"0")   # volta o hardware para o estado neutro
            time.sleep(0.2)
            ser.close()
        cam.parar()
        cv2.destroyAllWindows()
        print("[ok] encerrado")


if __name__ == "__main__":
    main()
