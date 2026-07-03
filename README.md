# EV Monitor

Projeto para monitoramento de utilização de eletropostos da Tupinambá Energia.

## Funcionalidades

- Consulta automática da API
- Armazena snapshots completos
- Detecta início e fim de carregamentos
- Calcula quantidade de sessões
- Dashboard em Streamlit
- Exportação em CSV

---

## Instalação

Clone o projeto

```bash
git clone https://github.com/SEUUSUARIO/ev-monitor.git
```

Crie um ambiente virtual

```bash
python -m venv .venv
```

Windows

```bash
.venv\Scripts\activate
```

Linux/Mac

```bash
source .venv/bin/activate
```

Instale as dependências

```bash
pip install -r requirements.txt
```

Copie

```
.env.example
```

para

```
.env
```

---

## Executando

Iniciar monitor

```bash
python scheduler.py
```

Dashboard

```bash
streamlit run dashboard.py
```

---

## Estrutura

```
data/
    snapshots/
    sessions.csv
    metrics.csv
```

---

## API utilizada

```
https://api.tupinambaenergia.com.br/station/{station_id}
```

---

Projeto desenvolvido apenas para fins de monitoramento e análise estatística.