#include <Servo.h>

const int PINO_SERVO = 9;
const int BUZZER     = 7;

const int H_IN1 = 3;
const int H_IN2 = 4;
const int H_ENA = 5;   

const bool ESTEIRA_2PINOS = false;  

const int US_PARADO = 1500;   // ponto neutro (ajuste fino aqui)
const int US_FECHAR = 2000;   // gira no sentido de fechar
const int US_ABRIR  = 1300;   // gira no sentido de abrir

const int MS_FECHAR = 500;    
const int MS_ABRIR  = 550;    

const int MS_PULSO  = 100;    // duracao dos pulsos de calibracao 'f' e 'a'

const int MS_BARREIRA = 2000; // tempo fechada antes de reabrir

// true  = esteira para enquanto a barreira esta fechada
// false = esteira continua andando (comporta desvia a fruta)
const bool PARAR_ESTEIRA_NO_DESCARTE = false;

const int VEL_ESTEIRA = 200;  
const int MS_PARADA   = 250;  

Servo barreira;
bool fechada       = false;
bool esteiraLigada = false;

void esteiraLigar() {
  if (ESTEIRA_2PINOS) {
    digitalWrite(H_IN1, LOW);
    analogWrite(H_ENA, VEL_ESTEIRA);
  } else {
    digitalWrite(H_IN1, HIGH);
    digitalWrite(H_IN2, LOW);
    analogWrite(H_ENA, VEL_ESTEIRA);
  }
  esteiraLigada = true;
}

void esteiraParar() {
  analogWrite(H_ENA, 0);
  digitalWrite(H_IN1, LOW);
  if (!ESTEIRA_2PINOS) digitalWrite(H_IN2, LOW);
  esteiraLigada = false;
}

void girar(int us, int ms) {
  barreira.attach(PINO_SERVO, 500, 2500);
  barreira.writeMicroseconds(us);
  delay(ms);
  barreira.writeMicroseconds(US_PARADO);
  delay(80);
  barreira.detach();
}

void fechar() {
  if (fechada) return;
  girar(US_FECHAR, MS_FECHAR);
  fechada = true;
}

void abrir() {
  if (!fechada) return;
  girar(US_ABRIR, MS_ABRIR);
  fechada = false;
}

void bipar(int vezes) {
  for (int i = 0; i < vezes; i++) {
    digitalWrite(BUZZER, HIGH);
    delay(120);
    digitalWrite(BUZZER, LOW);
    delay(80);
  }
}

void descartar() {
  if (PARAR_ESTEIRA_NO_DESCARTE) {
    esteiraParar();
    delay(MS_PARADA);
  }

  fechar();
  bipar(2);
  delay(MS_BARREIRA);
  abrir();

  if (!esteiraLigada) esteiraLigar();
}

void imprimirEstado() {
  Serial.print(F("barreira="));
  Serial.print(fechada ? F("FECHADA") : F("ABERTA"));
  Serial.print(F("  esteira="));
  Serial.println(esteiraLigada ? F("ON") : F("OFF"));
}

void setup() {
  pinMode(BUZZER, OUTPUT);
  digitalWrite(BUZZER, LOW);

  pinMode(H_IN1, OUTPUT);
  pinMode(H_IN2, OUTPUT);
  pinMode(H_ENA, OUTPUT);
  esteiraParar();

  Serial.begin(9600);

  girar(US_ABRIR, MS_ABRIR);
  fechada = false;

  bipar(1);          
  esteiraLigar();
}

void loop() {
  if (Serial.available() > 0) {
    char cmd = Serial.read();

    switch (cmd) {
      case 'V':
      case 'M':
        break;              

      case 'R':
        descartar();
        break;

      case '0':
        abrir();
        if (!esteiraLigada) esteiraLigar();
        break;

      // --- teste manual ---
      case 'L': esteiraLigar(); imprimirEstado(); break;
      case 'P': esteiraParar(); imprimirEstado(); break;
      case 'F': fechar();       imprimirEstado(); break;
      case 'A': abrir();        imprimirEstado(); break;

      // --- calibracao: pulsos curtos para medir o curso ---
      case 'f': girar(US_FECHAR, MS_PULSO); break;
      case 'a': girar(US_ABRIR,  MS_PULSO); break;

      // --- calibracao: ponto de parada ---
      case 'T':
        Serial.println(F("3s parado - nao pode girar nem tremer"));
        barreira.attach(PINO_SERVO, 500, 2500);
        barreira.writeMicroseconds(US_PARADO);
        delay(3000);
        barreira.detach();
        Serial.println(F("fim"));
        break;

      case '?': imprimirEstado(); break;

      default: break;   
    }
  }
}
