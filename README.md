# Classificador de Laranjas C1–C6

Sistema embarcado de classificação de maturação de laranjas por visão
computacional, com descarte físico automático das frutas deterioradas.

Uma câmera captura a fruta na esteira, uma rede YOLOv8 de classificação
determina o estágio de maturação (C1 a C6) e um Arduino aciona uma
barreira servo-acionada que bloqueia a passagem quando a laranja está
deteriorada (C6).

Projeto inicialmente desenvolvido para a disciplina de Inteligência Artificial do
curso de Engenharia de Computação — FACAMP e continuado na disciplina de Controle e Automação com a
contrusção da esteira e sistema embarcado.

---

## Arquitetura

```
  Celular (DroidCam)          Notebook                    Arduino Uno
  ┌──────────────┐      ┌──────────────────┐        ┌──────────────────┐
  │  câmera      │─────▶│ classificador_   │───────▶│ laranja_atuador  │
  │  MJPEG/HTTP  │      │ embarcado.py     │ serial │ .ino             │
  └──────────────┘      │                  │  9600  │                  │
                        │ YOLOv8-cls       │        │ ├─ servo         │
                        │ threshold 0.70   │        │ ├─ ponte H       │
                        │ janela temporal  │        │ └─ buzzer        │
                        │ cooldown         │        └──────────────────┘
                        └──────────────────┘
```

O lado Python decide **o que** a fruta é. O lado Arduino decide **como**
reagir fisicamente. A fronteira entre os dois é um protocolo de um byte,
o que mantém cada metade testável de forma independente.

---

## Estrutura do repositório

```
.
├── README.md
├── .gitignore
├── requirements.txt
├── classificador_embarcado.py      # inferência + comunicação serial
├── laranja_atuador/
│   └── laranja_atuador.ino         # firmware: servo, esteira, buzzer
└── modelo/
    └── best.pt                     # pesos treinados (ver seção Modelo)
```

---

## Modelo

- **Arquitetura:** YOLOv8-L classificação (`yolov8l-cls`), Ultralytics
- **Classes:** C1, C2, C3, C4, C5, C6 (C6 = deteriorada)
- **Dataset:** 2.544 imagens após limpeza, divisão estratificada 80/10/10
- **Acurácia no conjunto de teste:** 94,12%
- **Métricas da classe C6:** precisão = recall = F1 = 1,0
- **Treinamento:** Google Colab Pro, GPU L4
- **Resolução de entrada:** 224 px

O teto de desempenho observado (~96% em validação) foi interpretado como
ruído irredutível de rótulo: a maturação é um processo contínuo, e os
limites entre classes vizinhas (C3/C4, por exemplo) são inerentemente
difusos. Imagens duplicadas entre classes adjacentes foram removidas na
etapa de limpeza.

### Obtendo os pesos

O arquivo `best.pt` tem cerca de 73 MB. Escolha uma das duas abordagens:

**Git LFS**

```bash
git lfs install
git lfs track "*.pt"
git add .gitattributes
```

## Hardware

### Lista de materiais

- Arduino Uno + cabo USB-B
- Servo MG995 de **rotação contínua** (360°)
- Ponte H L298N, ou L9110S / MX1508
- Motor DC da esteira
- Buzzer ativo 5 V
- Bateria 18650 com shield de carga/boost
- Capacitor eletrolítico 1000 µF / 16 V
- Protoboard e jumpers
- Celular com DroidCam, ou webcam USB

### Pinagem

- Servo (sinal, fio laranja) → **D9**
- Buzzer (+) → **D7**
- Ponte H `IN1` → **D3**
- Ponte H `IN2` → **D4**
- Ponte H `ENA` → **D5** (PWM; retire o jumper do ENA na L298N)
- Ponte H `OUT1` / `OUT2` → terminais do motor da esteira

Para L9110S / MX1508: `IA` → D3, `IB` → D5, e defina
`ESTEIRA_2PINOS = true` no sketch.

### Alimentação

Regra central: **o servo nunca toca o 5 V do Arduino.**

- Shield 18650 `5V` → fio vermelho do servo
- Shield 18650 `GND` → fio marrom do servo
- Shield 18650 `GND` → `GND` do Arduino
- Ponte H `GND` → mesmo nó comum
- Capacitor de 1000 µF entre 5 V e GND, o mais perto possível do servo
- Arduino alimentado pelo USB do notebook

Os três GND formam um **nó comum em paralelo**, não em série. O sinal PWM
é uma tensão relativa ao GND: sem referência compartilhada o servo não
interpreta o pulso. E o retorno de corrente do servo, que passa de 1 A
nos picos, não deve atravessar a placa do Arduino.

A L298N tem queda interna de cerca de 2 V. Alimentada com 5 V, entrega
apenas ~3 V ao motor. Prefira 6–12 V na entrada de potência, ou use uma
L9110S, que tem queda desprezível.

---

## Protocolo serial

9600 baud, um byte por decisão, sem terminador.

| Byte | Classe       | Ação                                        |
|------|--------------|---------------------------------------------|
| `V`  | C1, C2       | imatura — passa, sem ação mecânica          |
| `M`  | C3, C4, C5   | madura — passa, sem ação mecânica           |
| `R`  | C6           | fecha a barreira, bipa, aguarda, reabre     |
| `0`  | indefinida   | garante barreira aberta e esteira ligada    |

Comandos adicionais, disponíveis apenas pelo Monitor Serial:

- `L` / `P` — liga e para a esteira
- `F` / `A` — fecha e abre a barreira
- `f` / `a` — pulsos de 100 ms, usados para medir o curso
- `T` — testa o ponto de parada do servo contínuo
- `?` — imprime o estado atual

---

## Instalação

```bash
git clone https://github.com/Genbaico/Ia-DetectorLaranjaEsteira
cd <A pasta em que baixou>

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

sudo usermod -aG dialout $USER    # logout/login depois
```

A instalação baixa o PyTorch com CUDA (vários GB). Em máquina com GPU
NVIDIA a inferência roda na GPU automaticamente.

Suba o firmware pela IDE do Arduino abrindo
`laranja_atuador/laranja_atuador.ino`.

---

## Uso

```bash
# apenas visão computacional, sem hardware
python classificador_embarcado.py --sem-arduino

# câmera do celular via DroidCam (Wi-Fi)
python classificador_embarcado.py --cam http://<Ip da Sua camera>:4747/video

# câmera do celular via USB
adb forward tcp:4747 tcp:4747
python classificador_embarcado.py --cam http://127.0.0.1:4747/video

# sistema completo
python classificador_embarcado.py \
    --cam http://127.0.0.1:4747/video \
    --porta /dev/ttyACM0
```

`q` encerra. Ao sair, o script envia `0` e devolve o hardware ao estado
de repouso.

### Parâmetros de decisão

Definidos no topo de `classificador_embarcado.py`:

- `CONF_MIN = 0.70` — descarta predições de baixa confiança
- `JANELA = 8`, `MIN_VOTOS = 6` — exige maioria em uma janela temporal,
  evitando que um frame ruim acione o hardware
- `COOLDOWN` — bloqueia novas decisões enquanto o ciclo mecânico anterior
  ainda está em curso. Deve ser maior que a duração do ciclo de descarte
- `ROI_FRACAO = 0.55` — recorte central do frame enviado ao modelo

A leitura da câmera roda em thread separada, mantendo apenas o frame mais
recente. Sem isso, o stream do DroidCam chega mais rápido do que a
inferência consome e a imagem acumula atraso.

---

## Calibração do servo contínuo

O MG995 de rotação contínua **não aceita comando de ângulo**. O valor
enviado define velocidade e sentido: `US_PARADO` é o repouso, valores
abaixo giram para um lado e acima para o outro. A posição é obtida
girando por um tempo calibrado.

Pelo Monitor Serial, nesta ordem:

1. `T` — o servo deve ficar imóvel por 3 s. Se derivar, ajuste
   `US_PARADO` de 5 em 5 (normalmente entre 1480 e 1520)
2. `f` — um pulso de 100 ms. Se o braço for para o lado errado, troque
   `US_FECHAR` e `US_ABRIR` entre si
3. `f` repetidamente — conte os pulsos até encostar no batente inferior.
   `MS_FECHAR` = (pulsos × 100) + folga
4. `a` repetidamente — o mesmo para `MS_ABRIR`

Mantenha `US_FECHAR` e `US_ABRIR` **simétricos** em relação a
`US_PARADO` (por exemplo 1700 e 1300). Velocidades diferentes nos dois
sentidos produzem cursos diferentes, e a diferença se acumula.

### Batentes mecânicos

Servo de rotação contínua não tem realimentação de posição, então erro
residual por ciclo vira erro grande após algumas repetições. A solução é
mecânica: instale um batente na posição aberta e dimensione `MS_ABRIR`
com sobra deliberada, de modo que toda abertura termine com o braço
encostado nele. A posição de repouso passa a ser definida pela mecânica,
e o erro é zerado a cada ciclo em vez de acumulado.

Use velocidade baixa no sentido de abertura para que o encontro com o
batente seja suave: servo empurrando batente em velocidade máxima puxa
corrente de travamento e derruba a tensão da bateria.

---

## Limitações conhecidas

- **Iluminação.** O modelo decide majoritariamente por cor. Luz
  incandescente amarelada desloca predições de C3 em direção a C4/C5.
  Use luz branca difusa, próxima às condições do dataset
- **Enquadramento.** O recorte central é fixo. Deslocar a câmera após a
  calibração reduz a confiança das predições
- **Servo de rotação contínua.** Sem batente mecânico, a posição de
  repouso deriva a cada ciclo. Um servo posicional de 180° seria a peça
  adequada para esta função
- **Classes vizinhas.** A fronteira entre estágios adjacentes é contínua
  por natureza; erros entre C3 e C4 são esperados e não indicam falha do
  sistema. A separação de C6, que é a decisão com consequência física, é
  perfeita no conjunto de teste

---

## Solução de problemas

- `could not open port /dev/ttyACM0: Device or resource busy` — Monitor
  Serial da IDE aberto, ou ModemManager sondando a porta. Feche o monitor
  e execute `sudo systemctl stop ModemManager`. `fuser -v /dev/ttyACM0`
  mostra quem está segurando
- `Connection timed out` na URL do DroidCam — dispositivos em redes
  diferentes, ou isolamento de clientes no Wi-Fi. Use o método via USB
  com `adb forward`
- Arduino reinicia quando o servo se move — GND não comum, ou capacitor
  ausente
- Esteira gira ao contrário — inverta os fios do motor na ponte H
- Avisos de Qt sobre plugin Wayland e fontes — inofensivos; o script já
  força `QT_QPA_PLATFORM=xcb`

---

## Metodologia

O desenvolvimento seguiu CRISP-DM, com versionamento explícito dos
treinos. Quatro versões foram treinadas; a V3 (`yolov8l-cls` com dataset
balanceado) foi selecionada como modelo final. A documentação acadêmica
completa está no artigo científico que acompanha o projeto, redigido
conforme as normas ABNT NBR 6022, 6023 e 14724.

## Integrantes do Grupo

| Nome | GitHub ou Linkedin | Role principal |
|---|---| --- |
| Henrique Radi (Eng de Comp.)   | [@Genbaico](https://github.com/Genbaico) | Treinamento da IA-Laranja e logica do embarcado | 
| Rafael Rodrigues (Eng de Comp.) | [@RafaelRodrigues1003](https://github.com/RafaelRodrigues1003) | Treinamento da IA-Laranja e logica do embarcado |
| Guilherme Prado (Eng de Prod.) | [LI-Guilherme Prado](https://www.linkedin.com/in/guilherme-prado-b3bb5437a?utm_source=share_via&utm_content=profile&utm_medium=member_io) | Construção da esteira |

