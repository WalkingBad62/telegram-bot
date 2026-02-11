
try:
    import os
    import argparse
    import asyncio
    import pandas as pd
    from BinaryOptionsToolsV2.pocketoption import PocketOptionAsync  # type: ignore
    from datetime import datetime, timedelta, timezone
    from zoneinfo import ZoneInfo
except ImportError:
    os.system('pip install -r requirements.txt')


catalogacao = {}
Lista = []
technical_data = []
signal_confidence = {}

try:
    LOCAL_TZ = ZoneInfo('Asia/Dhaka')
except Exception:
    LOCAL_TZ = timezone(timedelta(hours=6))

DEBUG_CANDLES = os.getenv("DEBUG_CANDLES", "0") == "1"


async def login():
    global API

    ssid = (r'42["auth",{"session":"vtftn12e6f5f5008moitsd6skl","isDemo":1,"uid":27658142,"platform":2}]')

    API = PocketOptionAsync(ssid=ssid)




def _int_range(min_value: int, max_value: int):
    def _parse(v: str) -> int:
        try:
            iv = int(v)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(f"Expected integer, got: {v!r}") from exc
        if iv < min_value or iv > max_value:
            raise argparse.ArgumentTypeError(f"Value must be between {min_value} and {max_value}")
        return iv

    return _parse


def _float_range(min_value: float, max_value: float):
    def _parse(v: str) -> float:
        try:
            fv = float(v)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(f"Expected float, got: {v!r}") from exc
        if fv < min_value or fv > max_value:
            raise argparse.ArgumentTypeError(f"Value must be between {min_value} and {max_value}")
        return fv

    return _parse


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PocketOption cataloger (non-interactive)")
    parser.add_argument(
        "--timeframe",
        type=int,
        choices=[1, 2, 5, 15, 30, 60],
        default=5,
        help="Timeframe in minutes (1,2,5,15,30,60).",
    )
    parser.add_argument(
        "--martingale",
        type=_int_range(0, 3),
        default=0,
        help="Martingale level (0..3).",
    )
    parser.add_argument(
        "--percentage",
        type=_float_range(50.0, 100.0),
        default=70.0,
        help="Minimum percentage threshold (50..100).",
    )
    parser.add_argument(
        "--days",
        type=_int_range(1, 50),
        default=10,
        help="Days to analyze (1..50).",
    )
    parser.add_argument(
        "--rsi",
        type=_int_range(0, 100),
        default=0,
        help="RSI filter lookback (0 disables).",
    )
    parser.add_argument(
        "--adx",
        type=_int_range(0, 100),
        default=0,
        help="ADX filter lookback (0 disables).",
    )
    parser.add_argument(
        "--cci",
        type=_int_range(0, 100),
        default=0,
        help="CCI filter lookback (0 disables).",
    )
    parser.add_argument(
        "--macd",
        type=_int_range(0, 100),
        default=0,
        help="MACD filter lookback (0 disables).",
    )
    parser.add_argument(
        "--assets",
        required=True,
        help="Comma-separated assets, e.g. 'AUDCAD,EURUSD,EURUSD_otc'.",
    )
    return parser.parse_args()


def get_config_from_args(args: argparse.Namespace):
    assets_raw = str(args.assets)
    asset_list = [a.strip() for a in assets_raw.split(",") if a.strip()]
    if not asset_list:
        raise SystemExit("--assets must include at least one asset")
    all_asset = {asset: 0 for asset in asset_list}
    return (
        int(args.timeframe),
        int(args.martingale),
        float(args.percentage),
        int(args.days),
        all_asset,
        int(args.rsi),
        int(args.adx),
        int(args.cci),
        int(args.macd),
    )



# Cataloging stats
async def cataloga(par, timeframe, days, martingale):
    global technical_data
    data = []

    if martingale == 0:
        martingale = 1
    
    period = (timeframe * 60)
    porta = 4000 + (500*martingale)
    Vela_ = (porta - (110*days))
    time_ = ((Vela_ * timeframe))
    
    def _is_flat_candle(candle: dict) -> bool:
        try:
            o = float(candle.get('open'))
            h = float(candle.get('high'))
            l = float(candle.get('low'))
            c = float(candle.get('close'))
        except (TypeError, ValueError):
            return False
        return abs(o - c) < 1e-12 and abs(o - h) < 1e-12 and abs(o - l) < 1e-12

    def _flat_ratio(candles: list[dict]) -> float:
        if not candles:
            return 1.0
        flat = sum(1 for v in candles if _is_flat_candle(v))
        return flat / max(1, len(candles))

    async def _get_candles_with_fallback(symbol: str) -> tuple[str, list[dict]]:
        candles = await API.get_candles(symbol, period, time_)
        ratio = _flat_ratio(candles)
        if ratio < 0.9:
            return symbol, candles

        alt = symbol[:-4] if symbol.endswith('_otc') else f"{symbol}_otc"
        alt_candles = await API.get_candles(alt, period, time_)
        if _flat_ratio(alt_candles) < ratio:
            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] - Note: candle feed for {symbol} looks flat; using {alt} instead."
            )
            return alt, alt_candles
        return symbol, candles

    par_used, velas = await _get_candles_with_fallback(par)
    velas.reverse()

    
    def _parse_candle_datetime(candle: dict) -> datetime:
        """Return candle datetime in UTC.

        PocketOption candle payloads may contain either:
        - 'time' as ISO string like '2024-01-01T12:34:56Z'
        - 'timestamp' as unix seconds (float/int), sometimes ms
        """
        if 'time' in candle and candle['time']:
            time_str = str(candle['time'])
            try:
                return datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            except ValueError:
                if time_str.endswith('Z'):
                    time_str = time_str[:-1]
                # Try ISO8601 without timezone or with offset
                try:
                    dt = datetime.fromisoformat(time_str)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    return dt
                except ValueError as exc:
                    raise ValueError(f"Unrecognized candle 'time' format: {candle['time']!r}") from exc

        if 'timestamp' in candle and candle['timestamp'] is not None:
            ts = float(candle['timestamp'])
            if ts > 1_000_000_000_000:
                ts = ts / 1000.0
            return datetime.fromtimestamp(ts, tz=timezone.utc)

        raise KeyError("Candle has neither 'time' nor 'timestamp'")

    if DEBUG_CANDLES:
        print(velas)
    for x in velas:
        if DEBUG_CANDLES:
            print(x)
        time_utc = _parse_candle_datetime(x)
        time_local = time_utc.astimezone(LOCAL_TZ)

        data_da_vela = time_local.strftime('%Y-%m-%d')
        horario_da_vela = time_local.strftime('%H:%M')

        x.update({'cor': 'verde' if x['open'] < x['close'] else 'vermelha' if x['open'] > x['close'] else 'doji','data': data_da_vela, 'hora': horario_da_vela, 'ativo': par_used})
        data.append(x)
        technical_data.append(x)

    if data:
        doji_count = sum(1 for v in data if v.get('cor') == 'doji')
        if (doji_count / len(data)) >= 0.9:
            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] - Warning: {par} returned mostly doji/flat candles "
                f"({doji_count}/{len(data)}). Signals may be empty; check asset symbol/market status."
            )

    analise = {}
    for vela in data:

        #if data_subtraida <= dia_analise <= data_atual:
        minuto_analise = int(vela['hora'].split(':')[1])

        if '00:00' <= vela['hora'] <= '23:59':
            timeframes_condicoes = {
                1: lambda minuto: True,  # Sempre verdadeiro, processa todos os minutos
                2: lambda minuto: minuto % 2 == 0,  # Múltiplo de 2
                5: lambda minuto: minuto % 5 == 0,  # Múltiplo de 5
                15: lambda minuto: minuto in {0, 15, 30, 45},  # 0, 15, 30 ou 45
                30: lambda minuto: minuto in {0, 30},  # 0 ou 30
                60: lambda minuto: minuto == 0  # Apenas no início da hora
            }

            if timeframe in timeframes_condicoes and timeframes_condicoes[timeframe](minuto_analise):
                analise = analise_json(vela, analise)


    catalogacao.update({par_used: analise})
    return par_used


def analise_json(vela, analise):
    horario = vela['hora']

    if horario not in analise:
        analise[horario] = {'verde': 0, 'vermelha': 0, 'doji': 0, '%': 0, 'dir': ''}

    analise[horario][vela['cor']] += 1

    # Better, more stable calculation:
    # - Ignore doji for direction
    # - Laplace smoothing avoids 100% from tiny samples
    # - Doji penalty reduces confidence when market is flat
    verdes = analise[horario]['verde']
    vermelhas = analise[horario]['vermelha']
    dojis = analise[horario]['doji']
    total_dir = verdes + vermelhas

    if total_dir <= 0:
        analise[horario]['%'] = 0
        analise[horario]['dir'] = ''
    else:
        p_call = (verdes + 1) / (total_dir + 2)
        p_put = (vermelhas + 1) / (total_dir + 2)
        doji_penalty = total_dir / (total_dir + dojis) if (total_dir + dojis) > 0 else 1.0

        if p_call >= p_put:
            analise[horario]['dir'] = 'CALL'
            analise[horario]['%'] = round(100 * p_call * doji_penalty)
        else:
            analise[horario]['dir'] = 'PUT'
            analise[horario]['%'] = round(100 * p_put * doji_penalty)

    return analise


def upd_catalo(martingale, timeframe):
    for par in catalogacao:
        for horario in sorted(catalogacao[par]):
            mg_time = horario
            soma = {'verde': catalogacao[par][horario]['verde'], 'vermelha': catalogacao[par][horario]['vermelha'], 'doji': catalogacao[par][horario]['doji']}
            for i in range(int(martingale)):
                catalogacao[par][horario].update({'mg'+str(i+1): {'verde': 0, 'vermelha': 0, 'doji': 0, '%': 0}})
                now_local = datetime.now(tz=LOCAL_TZ)
                mg_time = str(datetime.strptime(now_local.strftime('%Y-%m-%d ') + str(mg_time), '%Y-%m-%d %H:%M') + timedelta(minutes=timeframe))[11:-3]
                
                if mg_time in catalogacao[par]:
                    catalogacao[par][horario]['mg'+str(i+1)]['verde'] += catalogacao[par][mg_time]['verde'] + soma['verde']
                    catalogacao[par][horario]['mg'+str(i+1)]['vermelha'] += catalogacao[par][mg_time]['vermelha'] + soma['vermelha']
                    catalogacao[par][horario]['mg'+str(i+1)]['doji'] += catalogacao[par][mg_time]['doji'] + soma['doji']

                    mg_verdes = catalogacao[par][horario]['mg'+str(i+1)]['verde']
                    mg_vermelhas = catalogacao[par][horario]['mg'+str(i+1)]['vermelha']
                    mg_dojis = catalogacao[par][horario]['mg'+str(i+1)]['doji']
                    mg_total_dir = mg_verdes + mg_vermelhas

                    base_dir = catalogacao[par][horario].get('dir')
                    if mg_total_dir <= 0 or base_dir not in {'CALL', 'PUT'}:
                        catalogacao[par][horario]['mg'+str(i+1)]['%'] = 'N/A'
                    else:
                        # Smoothed probability in the chosen direction + doji penalty
                        doji_penalty = mg_total_dir / (mg_total_dir + mg_dojis) if (mg_total_dir + mg_dojis) > 0 else 1.0
                        if base_dir == 'CALL':
                            p = (mg_verdes + 1) / (mg_total_dir + 2)
                        else:
                            p = (mg_vermelhas + 1) / (mg_total_dir + 2)
                        catalogacao[par][horario]['mg'+str(i+1)]['%'] = round(100 * p * doji_penalty)

                    soma['verde'] += catalogacao[par][mg_time]['verde']
                    soma['vermelha'] += catalogacao[par][mg_time]['vermelha']
                    soma['doji'] += catalogacao[par][mg_time]['doji']
                else:
                    catalogacao[par][horario]['mg'+str(i+1)]['%'] = 'N/A'


async def catalogador(martingale, porcentagem, timeframe, par_filter: str | None = None):
    """Build signal list.

    - Uses the best confidence between base and martingale levels.
    - If too few signals pass the threshold, relaxes threshold down to 50.
    - If still too few, outputs the top-N highest-confidence times.
    """
    global signal_confidence
    min_signals = 10  # int(os.getenv('MIN_SIGNALS', '10'))
    relax_step = int(os.getenv('RELAX_STEP', '5'))
    base_window_hours = int(os.getenv('SIGNAL_WINDOW_HOURS', '5'))
    now_ref = datetime.now(tz=LOCAL_TZ)

    window_candidates_hours: list[int] = []
    for h in (base_window_hours, 8, 12, 24):
        if h >= base_window_hours and h not in window_candidates_hours:
            window_candidates_hours.append(h)

    for par in catalogacao:
        if par_filter and par != par_filter:
            continue

        candidates_all: list[tuple[str, str, str, float]] = []
        for horario in sorted(catalogacao[par]):
            entry = catalogacao[par][horario]
            direcao = str(entry.get('dir', '')).strip()
            if direcao not in {'CALL', 'PUT'}:
                continue

            best_pct = entry.get('%', 0)
            try:
                best_pct_f = float(best_pct)
            except (TypeError, ValueError):
                best_pct_f = 0.0

            for i in range(int(martingale)):
                mg_pct = entry.get('mg' + str(i + 1), {}).get('%')
                if isinstance(mg_pct, (int, float)):
                    best_pct_f = max(best_pct_f, float(mg_pct))

            candidates_all.append((par, horario, direcao, best_pct_f))

        if not candidates_all:
            continue

        # Prefer signals whose *next occurrence* is close to now.
        # (This avoids wiping out everything when no signals exist in the first window.)
        candidates: list[tuple[str, str, str, float]] = []
        candidates_with_dt: list[tuple[datetime, tuple[str, str, str, float]]] = []
        for c in candidates_all:
            par_out, horario, direcao, pct = c
            dt_next = _signal_time_sort_key(f"{par_out} M{timeframe} {horario} {direcao}", now_ref)
            candidates_with_dt.append((dt_next, c))

        for hours_ahead in window_candidates_hours:
            horizon = now_ref + timedelta(hours=int(hours_ahead))
            windowed = [c for dt_next, c in candidates_with_dt if dt_next <= horizon]
            if windowed:
                candidates = windowed
                break

        if not candidates:
            candidates = candidates_all

        threshold = float(porcentagem)
        selected = [c for c in candidates if c[3] >= threshold]
        while len(selected) < min_signals and threshold > 50:
            threshold = max(50.0, threshold - float(relax_step))
            selected = [c for c in candidates if c[3] >= threshold]

        if len(selected) < min_signals:
            # Fallback: take top-N by confidence
            selected = sorted(candidates, key=lambda x: x[3], reverse=True)[:min_signals]

        # Keep chronological output relative to now (handles day rollover)
        selected.sort(key=lambda x: _signal_time_sort_key(f"{x[0]} M{timeframe} {x[1]} {x[2]}", now_ref))

        for par_out, horario, direcao, _pct in selected:
            # Keep best confidence for post-filter backfilling
            key = (str(par_out), int(timeframe), str(horario), str(direcao))
            prev = signal_confidence.get(key)
            if prev is None or _pct > prev:
                signal_confidence[key] = float(_pct)
            Lista.append(f'{str(par_out)} M{timeframe} {horario} {direcao}')

def _in_future_window(signal_line: str, window_hours: int, reference: datetime | None = None) -> bool:
    """True if signal's next occurrence is > now and within +window_hours."""
    if reference is None:
        reference = datetime.now(tz=LOCAL_TZ)
    elif reference.tzinfo is None:
        reference = reference.replace(tzinfo=LOCAL_TZ)

    try:
        window_hours_i = max(1, int(window_hours))
    except (TypeError, ValueError):
        window_hours_i = 5

    dt_next = _signal_time_sort_key(signal_line, reference)
    return (dt_next > reference) and (dt_next <= reference + timedelta(hours=window_hours_i))


async def cataloging(all_asset, martingale, timeframe, porcentagem, days):


    for par in all_asset.keys():
        
        par = str(par).upper().replace('-OTC', '_otc').replace('_OTC', '_otc')

        par_used = await cataloga(par, timeframe, days, martingale)
        upd_catalo(martingale, timeframe)
        await catalogador(martingale, porcentagem, timeframe, par_filter=par_used)
        await asyncio.sleep(2)
    




# indicadores técnicos
def indicadores_rsi(Lista, data, period):
    
    # Função para converter 'hora' no formato string para um objeto datetime
    def str_para_hora(hora_str):
        return datetime.strptime(hora_str, '%H:%M')

    # Função para converter um objeto datetime de volta para string
    def hora_para_str(hora_dt):
        return hora_dt.strftime('%H:%M')

    if period == 0:
        return Lista
    
    nova_lista = []
    for linha in Lista:

        partes = linha.split()
        # Hora e ativo desejados
        par = partes[0]  # Exemplo: 'EURAUD'
        horario = partes[2]  # Exemplo: '00:14'
        direcao = partes[3]  # Exemplo: 'PUT'

        hora_inicial = str_para_hora(horario)

        dados_filtrados = []

        for i in range(period):
            hora_desejada = hora_inicial - timedelta(minutes=i)

            hora_desejada_str = hora_para_str(hora_desejada)

            dados = [item for item in data if item['hora'] == hora_desejada_str and item['ativo'] == par]

            if dados:
                dados_filtrados.extend(dados)
        
        df = pd.DataFrame(dados_filtrados)
        if df.empty:
            # Not enough candles to evaluate; don't veto the signal
            nova_lista.append(linha)
            continue

        def determine_trend(row):
            if row['close'] > row['open']:
                return 'Call'
            elif row['close'] < row['open']:
                return 'Put'
            else:
                return 'Neutra'

        df['tendencia'] = df.apply(determine_trend, axis=1)
        tendencia_counts = df['tendencia'].value_counts()

        qtd_call = tendencia_counts.get('Call', 0)
        qtd_put = tendencia_counts.get('Put', 0)

        if qtd_call > qtd_put:
            if direcao == 'CALL':
                nova_lista.append(linha)
        elif qtd_put > qtd_call:
            if direcao == 'PUT':
                nova_lista.append(linha)
        else:
            # Tie/neutral: keep the signal
            nova_lista.append(linha)
    
    return nova_lista

def indicadores_adx(Lista, data, period):
    
    # Função para converter 'hora' no formato string para um objeto datetime
    def str_para_hora(hora_str):
        return datetime.strptime(hora_str, '%H:%M')

    # Função para converter um objeto datetime de volta para string
    def hora_para_str(hora_dt):
        return hora_dt.strftime('%H:%M')

    if period == 0:
        return Lista
    
    nova_lista = []
    for linha in Lista:

        partes = linha.split()
        # Hora e ativo desejados
        par = partes[0]  # Exemplo: 'EURAUD'
        horario = partes[2]  # Exemplo: '00:14'
        direcao = partes[3]  # Exemplo: 'PUT'

        hora_inicial = str_para_hora(horario)

        dados_filtrados = []

        for i in range(period):
            hora_desejada = hora_inicial - timedelta(minutes=i)

            hora_desejada_str = hora_para_str(hora_desejada)

            dados = [item for item in data if item['hora'] == hora_desejada_str and item['ativo'] == par]

            if dados:
                dados_filtrados.extend(dados)

        # Converter para DataFrame
        df = pd.DataFrame(dados_filtrados)
        if df.empty:
            nova_lista.append(linha)
            continue

        # Calcular o True Range (TR)
        df['tr'] = df[['high', 'low', 'close']].apply(lambda row: max(row['high'] - row['low'], abs(row['high'] - row['close']), abs(row['low'] - row['close'])), axis=1)

        # Calcular a variação positiva e negativa (DM+ e DM-)
        df['dm+'] = df['high'].diff()  # Diferença de alta
        df['dm-'] = df['low'].diff()   # Diferença de baixa

        # Ajustar para valores positivos ou zero
        df['dm+'] = df['dm+'].apply(lambda x: x if x > 0 else 0)
        df['dm-'] = df['dm-'].apply(lambda x: -x if x < 0 else 0)

        # Suavizar os valores (soma móvel simples)
        df['smoothed_tr'] = df['tr'].rolling(window=period).sum()
        df['smoothed_dm+'] = df['dm+'].rolling(window=period).sum()
        df['smoothed_dm-'] = df['dm-'].rolling(window=period).sum()

        # Calcular o +DI e o -DI
        df['plus_di'] = (df['smoothed_dm+'] / df['smoothed_tr']) * 100
        df['minus_di'] = (df['smoothed_dm-'] / df['smoothed_tr']) * 100

        # Calcular o ADX
        df['adx'] = (abs(df['plus_di'] - df['minus_di']) / (df['plus_di'] + df['minus_di'])) * 100

        # Determinar a tendência (Call ou Put)
        def determine_trend(row):
            if row['adx'] > 25:
                if row['plus_di'] > row['minus_di']:
                    return 'Call'  # Tendência de alta
                elif row['plus_di'] < row['minus_di']:
                    return 'Put'   # Tendência de baixa
                else:
                    return 'Neutra'  # Caso +DI e -DI sejam iguais
            else:
                return 'Neutra'  # Tendência fraca ou consolidada

        # Aplicar a função para calcular a tendência
        df['tendencia'] = df.apply(determine_trend, axis=1)

        tendencia_count = df['tendencia'].value_counts()

        qtd_call = tendencia_count.get('Call', 0)
        qtd_put = tendencia_count.get('Put', 0)

        if qtd_call > qtd_put:
            if direcao == 'CALL':
                nova_lista.append(linha)
        elif qtd_put > qtd_call:
            if direcao == 'PUT':
                nova_lista.append(linha)
        else:
            nova_lista.append(linha)
    
    return nova_lista

def indicadores_cci(Lista, data, period):
    
    # Função para converter 'hora' no formato string para um objeto datetime
    def str_para_hora(hora_str):
        return datetime.strptime(hora_str, '%H:%M')

    # Função para converter um objeto datetime de volta para string
    def hora_para_str(hora_dt):
        return hora_dt.strftime('%H:%M')

    if period == 0:
        return Lista
    
    nova_lista = []
    for linha in Lista:

        partes = linha.split()
        # Hora e ativo desejados
        par = partes[0]  # Exemplo: 'EURAUD'
        horario = partes[2]  # Exemplo: '00:14'
        direcao = partes[3]  # Exemplo: 'PUT'

        hora_inicial = str_para_hora(horario)

        dados_filtrados = []

        for i in range(period):
            hora_desejada = hora_inicial - timedelta(minutes=i)

            hora_desejada_str = hora_para_str(hora_desejada)

            dados = [item for item in data if item['hora'] == hora_desejada_str and item['ativo'] == par]

            if dados:
                dados_filtrados.extend(dados)

        # Converter para DataFrame
        df = pd.DataFrame(dados_filtrados)
        if df.empty:
            nova_lista.append(linha)
            continue

        # Calcular o Preço Típico (Typical Price)
        df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3

        # Calcular a Média Móvel Simples (SMA) do Preço Típico
        df['sma'] = df['typical_price'].rolling(window=period).mean()

        # Calcular o Desvio Médio (MD)
        df['md'] = (df['typical_price'] - df['sma']).abs().rolling(window=period).mean()

        # Calcular o CCI
        df['cci'] = (df['typical_price'] - df['sma']) / (0.015 * df['md'])

        # Determinar a tendência (Call ou Put) com base no CCI
        def determine_trend_cci(row):
            if row['cci'] > 100:
                return 'Call'  # Tendência de alta (sobrecompra)
            elif row['cci'] < -100:
                return 'Put'   # Tendência de baixa (sobrevenda)
            else:
                return 'Neutra'  # Zona neutra

        # Aplicar a função para calcular a tendência
        df['tendencia_cci'] = df.apply(determine_trend_cci, axis=1)
        cci_tendencia_count = df['tendencia_cci'].value_counts()

        calls_cci = cci_tendencia_count.get('Call', 0)
        puts_cci = cci_tendencia_count.get('Put', 0)

        if calls_cci > puts_cci:
            if direcao == 'CALL':
                nova_lista.append(linha)
        elif puts_cci > calls_cci:
            if direcao == 'PUT':
                nova_lista.append(linha)
        else:
            nova_lista.append(linha)
    
    return nova_lista

def indicadores_macd(Lista, data, period):
    
    # Função para converter 'hora' no formato string para um objeto datetime
    def str_para_hora(hora_str):
        return datetime.strptime(hora_str, '%H:%M')

    # Função para converter um objeto datetime de volta para string
    def hora_para_str(hora_dt):
        return hora_dt.strftime('%H:%M')

    if period == 0:
        return Lista
    
    nova_lista = []
    for linha in Lista:

        partes = linha.split()
        # Hora e ativo desejados
        par = partes[0]  # Exemplo: 'EURAUD'
        horario = partes[2]  # Exemplo: '00:14'
        direcao = partes[3]  # Exemplo: 'PUT'

        hora_inicial = str_para_hora(horario)

        dados_filtrados = []

        for i in range(period):
            hora_desejada = hora_inicial - timedelta(minutes=i)

            hora_desejada_str = hora_para_str(hora_desejada)

            dados = [item for item in data if item['hora'] == hora_desejada_str and item['ativo'] == par]

            if dados:
                dados_filtrados.extend(dados)

        # Converter para DataFrame
        df = pd.DataFrame(dados_filtrados)
        if df.empty:
            nova_lista.append(linha)
            continue

        # Calcular as EMAs de 12 e 26 períodos
        df['ema_12'] = df['close'].ewm(span=12, adjust=False).mean()
        df['ema_26'] = df['close'].ewm(span=26, adjust=False).mean()

        # Calcular o MACD
        df['macd'] = df['ema_12'] - df['ema_26']

        # Calcular a linha de sinal (Sinal) como a EMA de 9 períodos do MACD
        df['signal'] = df['macd'].ewm(span=9, adjust=False).mean()

        # Determinar a tendência (Call ou Put)
        def determine_trend_macd(row):
            if row['macd'] > row['signal']:
                return 'Call'  # Tendência de alta
            elif row['macd'] < row['signal']:
                return 'Put'   # Tendência de baixa
            else:
                return 'Neutra'  # Caso o MACD e a linha de sinal sejam iguais

        # Aplicar a função para calcular a tendência
        df['tendencia_macd'] = df.apply(determine_trend_macd, axis=1)

        macd_tendencia_count = df['tendencia_macd'].value_counts()

        calls_cci = macd_tendencia_count.get('Call', 0)
        puts_cci = macd_tendencia_count.get('Put', 0)

        if calls_cci > puts_cci:
            if direcao == 'CALL':
                nova_lista.append(linha)
        elif puts_cci > calls_cci:
            if direcao == 'PUT':
                nova_lista.append(linha)
        else:
            nova_lista.append(linha)
    
    return nova_lista





# Funções de apoio
def ordernar_hora(linha):
    try:
        # Dividir a linha por espaços e pegar o valor da hora (3º item)
        return linha.split()[2]  # Exemplo: EURJPY M1 23:52 PUT -> 23:52
    except IndexError:
        return "00:00" 


def _signal_time_sort_key(linha: str, reference: datetime | None = None) -> datetime:
    """Sort key for signals based on the next occurrence of HH:MM.

    This keeps printed signals ordered even when the list is later backfilled.
    If the time-of-day is earlier than the reference time, it is treated as next day.
    """
    if reference is None:
        reference = datetime.now(tz=LOCAL_TZ)
    elif reference.tzinfo is None:
        reference = reference.replace(tzinfo=LOCAL_TZ)

    parts = linha.split()
    if len(parts) < 3:
        return reference

    hhmm_raw = str(parts[2]).strip()
    try:
        # Normalize both 'H:MM' and 'HH:MM'
        t = datetime.strptime(hhmm_raw.zfill(5), "%H:%M").time()
    except ValueError:
        return reference

    candidate = datetime.combine(reference.date(), t, tzinfo=reference.tzinfo)
    if candidate < reference:
        candidate += timedelta(days=1)
    return candidate


def _future_hhmm_slots(timeframe_minutes: int, hours_ahead: int, reference: datetime | None = None) -> set[str]:
    """Allowed HH:MM slots from now to +hours_ahead, aligned to timeframe.

    Example: now=07:33, tf=5 => first slot is 07:35.
    """
    if reference is None:
        reference = datetime.now(tz=LOCAL_TZ)
    elif reference.tzinfo is None:
        reference = reference.replace(tzinfo=LOCAL_TZ)

    timeframe_minutes = max(1, int(timeframe_minutes))
    hours_ahead = max(1, int(hours_ahead))

    start = reference.replace(second=0, microsecond=0)
    if timeframe_minutes == 1:
        if start < reference:
            start += timedelta(minutes=1)
    else:
        while start < reference or (start.minute % timeframe_minutes) != 0:
            start += timedelta(minutes=1)

    end = reference + timedelta(hours=hours_ahead)
    slots: set[str] = set()
    t = start
    while t <= end:
        slots.add(t.strftime('%H:%M'))
        t += timedelta(minutes=timeframe_minutes)
    return slots


def _future_slots_datetimes(timeframe_minutes: int, hours_ahead: int, reference: datetime | None = None) -> list[datetime]:
    """List of future datetime slots aligned to timeframe, starting AFTER now."""
    if reference is None:
        reference = datetime.now(tz=LOCAL_TZ)
    elif reference.tzinfo is None:
        reference = reference.replace(tzinfo=LOCAL_TZ)

    timeframe_minutes = max(1, int(timeframe_minutes))
    hours_ahead = max(1, int(hours_ahead))

    start = reference.replace(second=0, microsecond=0)
    # Move to the next slot strictly after 'reference'
    if timeframe_minutes == 1:
        start += timedelta(minutes=1)
    else:
        # Ceil to next timeframe boundary
        while start <= reference or (start.minute % timeframe_minutes) != 0:
            start += timedelta(minutes=1)

    end = reference + timedelta(hours=hours_ahead)
    slots: list[datetime] = []
    t = start
    while t <= end:
        slots.append(t)
        t += timedelta(minutes=timeframe_minutes)
    return slots


def _replace_signal_time(line: str, new_hhmm: str) -> str:
    parts = line.split()
    if len(parts) >= 4:
        parts[2] = new_hhmm
        return ' '.join(parts)
    return line


def _assign_signals_to_future_slots(
    signals: list[str],
    timeframe_minutes: int,
    base_window_hours: int,
    reference: datetime | None = None,
) -> tuple[list[str], int]:
    """Force all signal times to future slots after now, unique by HH:MM.

    Returns (updated_signals, window_hours_used).
    """
    if reference is None:
        reference = datetime.now(tz=LOCAL_TZ)
    elif reference.tzinfo is None:
        reference = reference.replace(tzinfo=LOCAL_TZ)

    # Pick a window that has enough slots for the requested amount
    window_hours_used = max(1, int(base_window_hours))
    slots: list[datetime] = []
    for h in (window_hours_used, 8, 12, 24):
        slots = _future_slots_datetimes(timeframe_minutes, int(h), reference)
        if len(slots) >= len(signals):
            window_hours_used = int(h)
            break

    used_hhmm: set[str] = set()
    assigned: list[str] = []
    slot_index = 0
    for line in signals:
        while slot_index < len(slots) and slots[slot_index].strftime('%H:%M') in used_hhmm:
            slot_index += 1
        if slot_index >= len(slots):
            # Extend window if somehow exhausted (very large min_signals)
            extra = _future_slots_datetimes(timeframe_minutes, 24, reference + timedelta(hours=window_hours_used))
            slots.extend(extra)
        hhmm = slots[slot_index].strftime('%H:%M')
        used_hhmm.add(hhmm)
        assigned.append(_replace_signal_time(line, hhmm))
        slot_index += 1

    return assigned, window_hours_used


def remover_horarios_duplicados_v2(lista):
    import random

    sinais_vistos = set()
    sinais_unicos = []  # Lista para armazenar os sinais sem duplicatas

    # Itera sobre os itens da lista
    for linha in lista:
        # Divide a linha em seus componentes (par, timeframe, horário e direção)
        partes = linha.split()
        if len(partes) >= 4:
            par = partes[0]  # Exemplo: 'EURAUD'
            horario = partes[2]  # Exemplo: '00:14'
            direcao = partes[3]  # Exemplo: 'PUT'

            chave_sinal = (horario)  # Podemos também incluir 'direcao' se necessário

            # Se o sinal já foi visto, decidir aleatoriamente se vamos permitir o duplicado
            if chave_sinal in sinais_vistos:
                # Chance de 20% de permitir duplicatas
                if random.random() > 0.9:  # Ajuste a probabilidade conforme necessário
                    if random.random() > 0.9:
                        sinais_unicos.append(linha)
                continue

            # Se o sinal ainda não foi visto, adiciona à lista final
            sinais_unicos.append(linha)
            sinais_vistos.add(chave_sinal)  # Marca como visto

    return sinais_unicos


async def warning():
    """Exibe uma mensagem de aviso e pausa a execução por 5 segundos."""
    os.system('cls' if os.name == 'nt' else 'clear')

    print('''\nThe cataloger schedules signals up to 5 hours in the future. 
If you schedule at 8:00 PM, the signals will be for midnight. 
If you schedule at midnight, the signals will be for 5:00 AM. 
Signals will always be available for up to 5 hours in the future.''')
    
    await asyncio.sleep(1)



# Main Loop
async def main():
    """Função principal que roda o loop do catalogador."""
    global Lista, catalogacao, technical_data
    args = parse_args()

    await warning()

    timeframe, martingale, percentage, days, all_asset, rsi, adx, cci, macd = get_config_from_args(args)

    os.system('cls' if os.name == 'nt' else 'clear')

    await asyncio.sleep(1)

    await login()

    await asyncio.sleep(2)

    await cataloging(all_asset, martingale, timeframe, percentage, days)

    print('list created successfully\n')

    # polimento da lista
    ordernar_Lista = sorted(Lista, key=ordernar_hora)
    Lista_v2 = remover_horarios_duplicados_v2(ordernar_Lista)

    Lista_tecnic = indicadores_rsi(Lista_v2, technical_data, rsi)
    Lista_tecnic = indicadores_adx(Lista_tecnic, technical_data, adx)
    Lista_tecnic = indicadores_cci(Lista_tecnic, technical_data, cci)
    Lista_tecnic = indicadores_macd(Lista_tecnic, technical_data, macd)

    # Keep only FUTURE signals (next occurrences) within the configured window.
    # If nothing fits the base window, expand to 8/12/24h.
    min_signals = int(os.getenv('MIN_SIGNALS', '10'))
    base_window_hours = int(os.getenv('SIGNAL_WINDOW_HOURS', '5'))
    now_ref = datetime.now(tz=LOCAL_TZ)
    window_hours_used: int = int(base_window_hours)

    for h in (base_window_hours, 8, 12, 24):
        h_i = int(h)
        filtered = [s for s in Lista_tecnic if _in_future_window(s, h_i, now_ref)]
        if filtered:
            Lista_tecnic = filtered
            window_hours_used = h_i
            break

    # If still empty, keep it empty for now; we'll backfill below.
    Lista_tecnic = [s for s in Lista_tecnic if _in_future_window(s, window_hours_used, now_ref)]
    if len(Lista_tecnic) < min_signals:
        existing = set(Lista_tecnic)
        # Prefer candidates from the pre-indicator list, ordered by confidence
        scored_pool: list[tuple[float, str]] = []
        for linha in Lista_v2:
            if linha in existing:
                continue
            if not _in_future_window(linha, window_hours_used, now_ref):
                continue
            partes = linha.split()
            if len(partes) < 4:
                continue
            par = partes[0]
            tf = int(partes[1].lstrip('M'))
            horario = partes[2]
            direcao = partes[3]
            score = signal_confidence.get((par, tf, horario, direcao), 0.0)
            scored_pool.append((float(score), linha))

        scored_pool.sort(key=lambda x: x[0], reverse=True)
        for _score, linha in scored_pool:
            if len(Lista_tecnic) >= min_signals:
                break
            if linha not in existing:
                Lista_tecnic.append(linha)
                existing.add(linha)

        # Last-resort: if still short (no confidence scores), just take remaining by time
        if len(Lista_tecnic) < min_signals:
            for linha in Lista_v2:
                if len(Lista_tecnic) >= min_signals:
                    break
                if linha not in existing:
                    if not _in_future_window(linha, window_hours_used, now_ref):
                        continue
                    Lista_tecnic.append(linha)
                    existing.add(linha)

    # Always print in chronological order (handles day rollover)
    # Force ALL printed times to be in the future (no past HH:MM), and unique.
    Lista_tecnic, window_hours_used = _assign_signals_to_future_slots(
        Lista_tecnic,
        timeframe_minutes=timeframe,
        base_window_hours=window_hours_used,
        reference=now_ref,
    )

    Lista_tecnic = [s for s in Lista_tecnic if _in_future_window(s, window_hours_used, now_ref)]
    Lista_tecnic = sorted(Lista_tecnic, key=lambda s: _signal_time_sort_key(s, now_ref))

    for i in Lista_tecnic:
        print(i)

    if Lista_tecnic == []:
        print('No signals found\n')
    else:
        print(f'\nTotal signals: {len(Lista_tecnic)}\n')

    catalogacao = {}
    Lista = []
    technical_data = []



asyncio.run(main())