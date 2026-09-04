-- pg_dump -h localhost -U postgres -d postgres \
--  --schema-only \
--  --file=D:\Work\workspace\python-space\fetch-angel-data\db_backup\datamodels_ddl.sql

--
-- PostgreSQL database dump
--

\restrict 2L0lN0qX9ydMVMMsQJmGZw75brZB0mInJAUBrhFG0BkrMDbfHaKHGkoNBcwJfb4

-- Dumped from database version 18.6
-- Dumped by pg_dump version 18.6

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: bhavcopy_progress; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.bhavcopy_progress (
    trade_date date NOT NULL,
    contracts_written integer,
    processed_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.bhavcopy_progress OWNER TO postgres;

--
-- Name: candles_1min; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.candles_1min (
    instrument_id bigint NOT NULL,
    ts timestamp with time zone NOT NULL,
    open numeric(12,4) NOT NULL,
    high numeric(12,4) NOT NULL,
    low numeric(12,4) NOT NULL,
    close numeric(12,4) NOT NULL,
    volume bigint DEFAULT 0,
    open_interest bigint
)
PARTITION BY RANGE (ts);


ALTER TABLE public.candles_1min OWNER TO postgres;

--
-- Name: candles_1min_2026_02; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.candles_1min_2026_02 (
    instrument_id bigint CONSTRAINT candles_1min_instrument_id_not_null NOT NULL,
    ts timestamp with time zone CONSTRAINT candles_1min_ts_not_null NOT NULL,
    open numeric(12,4) CONSTRAINT candles_1min_open_not_null NOT NULL,
    high numeric(12,4) CONSTRAINT candles_1min_high_not_null NOT NULL,
    low numeric(12,4) CONSTRAINT candles_1min_low_not_null NOT NULL,
    close numeric(12,4) CONSTRAINT candles_1min_close_not_null NOT NULL,
    volume bigint DEFAULT 0,
    open_interest bigint
);


ALTER TABLE public.candles_1min_2026_02 OWNER TO postgres;

--
-- Name: candles_1min_2026_03; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.candles_1min_2026_03 (
    instrument_id bigint CONSTRAINT candles_1min_instrument_id_not_null NOT NULL,
    ts timestamp with time zone CONSTRAINT candles_1min_ts_not_null NOT NULL,
    open numeric(12,4) CONSTRAINT candles_1min_open_not_null NOT NULL,
    high numeric(12,4) CONSTRAINT candles_1min_high_not_null NOT NULL,
    low numeric(12,4) CONSTRAINT candles_1min_low_not_null NOT NULL,
    close numeric(12,4) CONSTRAINT candles_1min_close_not_null NOT NULL,
    volume bigint DEFAULT 0,
    open_interest bigint
);


ALTER TABLE public.candles_1min_2026_03 OWNER TO postgres;

--
-- Name: candles_1min_2026_04; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.candles_1min_2026_04 (
    instrument_id bigint CONSTRAINT candles_1min_instrument_id_not_null NOT NULL,
    ts timestamp with time zone CONSTRAINT candles_1min_ts_not_null NOT NULL,
    open numeric(12,4) CONSTRAINT candles_1min_open_not_null NOT NULL,
    high numeric(12,4) CONSTRAINT candles_1min_high_not_null NOT NULL,
    low numeric(12,4) CONSTRAINT candles_1min_low_not_null NOT NULL,
    close numeric(12,4) CONSTRAINT candles_1min_close_not_null NOT NULL,
    volume bigint DEFAULT 0,
    open_interest bigint
);


ALTER TABLE public.candles_1min_2026_04 OWNER TO postgres;

--
-- Name: candles_1min_2026_05; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.candles_1min_2026_05 (
    instrument_id bigint CONSTRAINT candles_1min_instrument_id_not_null NOT NULL,
    ts timestamp with time zone CONSTRAINT candles_1min_ts_not_null NOT NULL,
    open numeric(12,4) CONSTRAINT candles_1min_open_not_null NOT NULL,
    high numeric(12,4) CONSTRAINT candles_1min_high_not_null NOT NULL,
    low numeric(12,4) CONSTRAINT candles_1min_low_not_null NOT NULL,
    close numeric(12,4) CONSTRAINT candles_1min_close_not_null NOT NULL,
    volume bigint DEFAULT 0,
    open_interest bigint
);


ALTER TABLE public.candles_1min_2026_05 OWNER TO postgres;

--
-- Name: candles_1min_2026_06; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.candles_1min_2026_06 (
    instrument_id bigint CONSTRAINT candles_1min_instrument_id_not_null NOT NULL,
    ts timestamp with time zone CONSTRAINT candles_1min_ts_not_null NOT NULL,
    open numeric(12,4) CONSTRAINT candles_1min_open_not_null NOT NULL,
    high numeric(12,4) CONSTRAINT candles_1min_high_not_null NOT NULL,
    low numeric(12,4) CONSTRAINT candles_1min_low_not_null NOT NULL,
    close numeric(12,4) CONSTRAINT candles_1min_close_not_null NOT NULL,
    volume bigint DEFAULT 0,
    open_interest bigint
);


ALTER TABLE public.candles_1min_2026_06 OWNER TO postgres;

--
-- Name: candles_1min_2026_07; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.candles_1min_2026_07 (
    instrument_id bigint CONSTRAINT candles_1min_instrument_id_not_null NOT NULL,
    ts timestamp with time zone CONSTRAINT candles_1min_ts_not_null NOT NULL,
    open numeric(12,4) CONSTRAINT candles_1min_open_not_null NOT NULL,
    high numeric(12,4) CONSTRAINT candles_1min_high_not_null NOT NULL,
    low numeric(12,4) CONSTRAINT candles_1min_low_not_null NOT NULL,
    close numeric(12,4) CONSTRAINT candles_1min_close_not_null NOT NULL,
    volume bigint DEFAULT 0,
    open_interest bigint
);


ALTER TABLE public.candles_1min_2026_07 OWNER TO postgres;

--
-- Name: candles_1min_2026_08; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.candles_1min_2026_08 (
    instrument_id bigint CONSTRAINT candles_1min_instrument_id_not_null NOT NULL,
    ts timestamp with time zone CONSTRAINT candles_1min_ts_not_null NOT NULL,
    open numeric(12,4) CONSTRAINT candles_1min_open_not_null NOT NULL,
    high numeric(12,4) CONSTRAINT candles_1min_high_not_null NOT NULL,
    low numeric(12,4) CONSTRAINT candles_1min_low_not_null NOT NULL,
    close numeric(12,4) CONSTRAINT candles_1min_close_not_null NOT NULL,
    volume bigint DEFAULT 0,
    open_interest bigint
);


ALTER TABLE public.candles_1min_2026_08 OWNER TO postgres;

--
-- Name: candles_1min_2026_09; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.candles_1min_2026_09 (
    instrument_id bigint CONSTRAINT candles_1min_instrument_id_not_null NOT NULL,
    ts timestamp with time zone CONSTRAINT candles_1min_ts_not_null NOT NULL,
    open numeric(12,4) CONSTRAINT candles_1min_open_not_null NOT NULL,
    high numeric(12,4) CONSTRAINT candles_1min_high_not_null NOT NULL,
    low numeric(12,4) CONSTRAINT candles_1min_low_not_null NOT NULL,
    close numeric(12,4) CONSTRAINT candles_1min_close_not_null NOT NULL,
    volume bigint DEFAULT 0,
    open_interest bigint
);


ALTER TABLE public.candles_1min_2026_09 OWNER TO postgres;

--
-- Name: exchanges; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.exchanges (
    id smallint NOT NULL,
    code text NOT NULL
);


ALTER TABLE public.exchanges OWNER TO postgres;

--
-- Name: exchanges_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.exchanges_id_seq
    AS smallint
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.exchanges_id_seq OWNER TO postgres;

--
-- Name: exchanges_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.exchanges_id_seq OWNED BY public.exchanges.id;


--
-- Name: expired_options; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.expired_options (
    id bigint NOT NULL,
    symbol character varying(50) NOT NULL,
    instrument_type character varying(20) NOT NULL,
    underlying_symbol character varying(20) NOT NULL,
    expiry_date date NOT NULL,
    strike numeric(10,2) NOT NULL,
    "timestamp" timestamp without time zone NOT NULL,
    open numeric(12,4),
    high numeric(12,4),
    low numeric(12,4),
    close numeric(12,4),
    volume bigint,
    open_interest bigint,
    nifty_spot numeric(12,4),
    atm_strike numeric(10,2),
    fetched_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    data_source character varying(50) DEFAULT 'openchart'::character varying,
    is_expired boolean DEFAULT true
);


ALTER TABLE public.expired_options OWNER TO postgres;

--
-- Name: expired_options_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.expired_options_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.expired_options_id_seq OWNER TO postgres;

--
-- Name: expired_options_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.expired_options_id_seq OWNED BY public.expired_options.id;


--
-- Name: ingestion_progress; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.ingestion_progress (
    instrument_id bigint NOT NULL,
    "interval" text NOT NULL,
    chunk_start date NOT NULL,
    completed_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.ingestion_progress OWNER TO postgres;

--
-- Name: instruments; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.instruments (
    id bigint NOT NULL,
    exchange_id smallint NOT NULL,
    instrument_token bigint,
    trading_symbol text NOT NULL,
    name text,
    instrument_type text NOT NULL,
    underlying_symbol text NOT NULL,
    expiry date,
    strike numeric(12,2),
    lot_size integer,
    tick_size numeric(8,4),
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT instruments_instrument_type_check CHECK ((instrument_type = ANY (ARRAY['INDEX'::text, 'EQ'::text, 'FUT'::text, 'CE'::text, 'PE'::text])))
);


ALTER TABLE public.instruments OWNER TO postgres;

--
-- Name: instruments_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.instruments_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.instruments_id_seq OWNER TO postgres;

--
-- Name: instruments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.instruments_id_seq OWNED BY public.instruments.id;


--
-- Name: nifty50_cleanup_backup_candles_20260904; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.nifty50_cleanup_backup_candles_20260904 (
    instrument_id bigint,
    ts timestamp with time zone,
    open numeric(12,4),
    high numeric(12,4),
    low numeric(12,4),
    close numeric(12,4),
    volume bigint,
    open_interest bigint
);


ALTER TABLE public.nifty50_cleanup_backup_candles_20260904 OWNER TO postgres;

--
-- Name: nifty50_cleanup_backup_instruments_20260904; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.nifty50_cleanup_backup_instruments_20260904 (
    id bigint,
    exchange_id smallint,
    instrument_token bigint,
    trading_symbol text,
    name text,
    instrument_type text,
    underlying_symbol text,
    expiry date,
    strike numeric(12,2),
    lot_size integer,
    tick_size numeric(8,4),
    is_active boolean,
    created_at timestamp with time zone
);


ALTER TABLE public.nifty50_cleanup_backup_instruments_20260904 OWNER TO postgres;

--
-- Name: nifty_expiry_calendar; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.nifty_expiry_calendar (
    expiry_date date NOT NULL,
    scheduled_date date NOT NULL,
    expiry_type character varying(20) NOT NULL,
    underlying character varying(30) DEFAULT 'NIFTY'::character varying NOT NULL,
    exchange character varying(20) DEFAULT 'NSE'::character varying NOT NULL,
    was_holiday_shift boolean DEFAULT false NOT NULL,
    shifted_from_holiday date,
    source text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.nifty_expiry_calendar OWNER TO postgres;

--
-- Name: nifty_options_data; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.nifty_options_data (
    id bigint NOT NULL,
    symbol character varying(50) NOT NULL,
    instrument_type character varying(20) NOT NULL,
    underlying_symbol character varying(20) NOT NULL,
    expiry_date date NOT NULL,
    strike numeric(10,2) NOT NULL,
    "timestamp" timestamp without time zone NOT NULL,
    nifty_spot numeric(12,4),
    atm_strike numeric(10,2),
    ltp numeric(12,4),
    iv numeric(8,4),
    volume bigint,
    open_interest bigint,
    oi_change bigint,
    oi_change_pct numeric(8,4),
    fetched_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    data_source character varying(50) DEFAULT 'nse_client'::character varying,
    is_expired boolean DEFAULT false
);


ALTER TABLE public.nifty_options_data OWNER TO postgres;

--
-- Name: nifty_options_data_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.nifty_options_data_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.nifty_options_data_id_seq OWNER TO postgres;

--
-- Name: nifty_options_data_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.nifty_options_data_id_seq OWNED BY public.nifty_options_data.id;


--
-- Name: nse_holidays; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.nse_holidays (
    holiday_date date NOT NULL,
    holiday_name text NOT NULL,
    segment character varying(20) DEFAULT 'ALL'::character varying NOT NULL,
    source text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.nse_holidays OWNER TO postgres;

--
-- Name: candles_1min_2026_02; Type: TABLE ATTACH; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.candles_1min ATTACH PARTITION public.candles_1min_2026_02 FOR VALUES FROM ('2026-02-01 00:00:00+05:30') TO ('2026-03-01 00:00:00+05:30');


--
-- Name: candles_1min_2026_03; Type: TABLE ATTACH; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.candles_1min ATTACH PARTITION public.candles_1min_2026_03 FOR VALUES FROM ('2026-03-01 00:00:00+05:30') TO ('2026-04-01 00:00:00+05:30');


--
-- Name: candles_1min_2026_04; Type: TABLE ATTACH; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.candles_1min ATTACH PARTITION public.candles_1min_2026_04 FOR VALUES FROM ('2026-04-01 00:00:00+05:30') TO ('2026-05-01 00:00:00+05:30');


--
-- Name: candles_1min_2026_05; Type: TABLE ATTACH; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.candles_1min ATTACH PARTITION public.candles_1min_2026_05 FOR VALUES FROM ('2026-05-01 00:00:00+05:30') TO ('2026-06-01 00:00:00+05:30');


--
-- Name: candles_1min_2026_06; Type: TABLE ATTACH; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.candles_1min ATTACH PARTITION public.candles_1min_2026_06 FOR VALUES FROM ('2026-06-01 00:00:00+05:30') TO ('2026-07-01 00:00:00+05:30');


--
-- Name: candles_1min_2026_07; Type: TABLE ATTACH; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.candles_1min ATTACH PARTITION public.candles_1min_2026_07 FOR VALUES FROM ('2026-07-01 00:00:00+05:30') TO ('2026-08-01 00:00:00+05:30');


--
-- Name: candles_1min_2026_08; Type: TABLE ATTACH; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.candles_1min ATTACH PARTITION public.candles_1min_2026_08 FOR VALUES FROM ('2026-08-01 00:00:00+05:30') TO ('2026-09-01 00:00:00+05:30');


--
-- Name: candles_1min_2026_09; Type: TABLE ATTACH; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.candles_1min ATTACH PARTITION public.candles_1min_2026_09 FOR VALUES FROM ('2026-09-01 00:00:00+05:30') TO ('2026-10-01 00:00:00+05:30');


--
-- Name: exchanges id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.exchanges ALTER COLUMN id SET DEFAULT nextval('public.exchanges_id_seq'::regclass);


--
-- Name: expired_options id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.expired_options ALTER COLUMN id SET DEFAULT nextval('public.expired_options_id_seq'::regclass);


--
-- Name: instruments id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.instruments ALTER COLUMN id SET DEFAULT nextval('public.instruments_id_seq'::regclass);


--
-- Name: nifty_options_data id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.nifty_options_data ALTER COLUMN id SET DEFAULT nextval('public.nifty_options_data_id_seq'::regclass);


--
-- Name: bhavcopy_progress bhavcopy_progress_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.bhavcopy_progress
    ADD CONSTRAINT bhavcopy_progress_pkey PRIMARY KEY (trade_date);


--
-- Name: candles_1min candles_1min_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.candles_1min
    ADD CONSTRAINT candles_1min_pkey PRIMARY KEY (instrument_id, ts);


--
-- Name: candles_1min_2026_02 candles_1min_2026_02_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.candles_1min_2026_02
    ADD CONSTRAINT candles_1min_2026_02_pkey PRIMARY KEY (instrument_id, ts);


--
-- Name: candles_1min_2026_03 candles_1min_2026_03_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.candles_1min_2026_03
    ADD CONSTRAINT candles_1min_2026_03_pkey PRIMARY KEY (instrument_id, ts);


--
-- Name: candles_1min_2026_04 candles_1min_2026_04_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.candles_1min_2026_04
    ADD CONSTRAINT candles_1min_2026_04_pkey PRIMARY KEY (instrument_id, ts);


--
-- Name: candles_1min_2026_05 candles_1min_2026_05_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.candles_1min_2026_05
    ADD CONSTRAINT candles_1min_2026_05_pkey PRIMARY KEY (instrument_id, ts);


--
-- Name: candles_1min_2026_06 candles_1min_2026_06_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.candles_1min_2026_06
    ADD CONSTRAINT candles_1min_2026_06_pkey PRIMARY KEY (instrument_id, ts);


--
-- Name: candles_1min_2026_07 candles_1min_2026_07_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.candles_1min_2026_07
    ADD CONSTRAINT candles_1min_2026_07_pkey PRIMARY KEY (instrument_id, ts);


--
-- Name: candles_1min_2026_08 candles_1min_2026_08_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.candles_1min_2026_08
    ADD CONSTRAINT candles_1min_2026_08_pkey PRIMARY KEY (instrument_id, ts);


--
-- Name: candles_1min_2026_09 candles_1min_2026_09_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.candles_1min_2026_09
    ADD CONSTRAINT candles_1min_2026_09_pkey PRIMARY KEY (instrument_id, ts);


--
-- Name: exchanges exchanges_code_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.exchanges
    ADD CONSTRAINT exchanges_code_key UNIQUE (code);


--
-- Name: exchanges exchanges_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.exchanges
    ADD CONSTRAINT exchanges_pkey PRIMARY KEY (id);


--
-- Name: expired_options expired_options_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.expired_options
    ADD CONSTRAINT expired_options_pkey PRIMARY KEY (id);


--
-- Name: ingestion_progress ingestion_progress_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ingestion_progress
    ADD CONSTRAINT ingestion_progress_pkey PRIMARY KEY (instrument_id, "interval", chunk_start);


--
-- Name: instruments instruments_exchange_id_trading_symbol_expiry_strike_instru_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.instruments
    ADD CONSTRAINT instruments_exchange_id_trading_symbol_expiry_strike_instru_key UNIQUE (exchange_id, trading_symbol, expiry, strike, instrument_type);


--
-- Name: instruments instruments_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.instruments
    ADD CONSTRAINT instruments_pkey PRIMARY KEY (id);


--
-- Name: nifty_expiry_calendar nifty_expiry_calendar_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.nifty_expiry_calendar
    ADD CONSTRAINT nifty_expiry_calendar_pkey PRIMARY KEY (expiry_date);


--
-- Name: nifty_options_data nifty_options_data_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.nifty_options_data
    ADD CONSTRAINT nifty_options_data_pkey PRIMARY KEY (id);


--
-- Name: nse_holidays nse_holidays_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.nse_holidays
    ADD CONSTRAINT nse_holidays_pkey PRIMARY KEY (holiday_date, segment);


--
-- Name: idx_expired_options_expiry; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_expired_options_expiry ON public.expired_options USING btree (expiry_date);


--
-- Name: idx_expired_options_expiry_strike; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_expired_options_expiry_strike ON public.expired_options USING btree (expiry_date, strike);


--
-- Name: idx_expired_options_strike; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_expired_options_strike ON public.expired_options USING btree (strike);


--
-- Name: idx_expired_options_symbol; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_expired_options_symbol ON public.expired_options USING btree (symbol);


--
-- Name: idx_expired_options_timestamp; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_expired_options_timestamp ON public.expired_options USING btree ("timestamp");


--
-- Name: idx_ingestion_progress_pending; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_ingestion_progress_pending ON public.ingestion_progress USING btree ("interval", instrument_id, chunk_start) WHERE (completed_at IS NULL);


--
-- Name: idx_instruments_type; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_instruments_type ON public.instruments USING btree (instrument_type);


--
-- Name: idx_instruments_underlying; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_instruments_underlying ON public.instruments USING btree (underlying_symbol, instrument_type, expiry);


--
-- Name: idx_nifty_expiry_type_date; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_nifty_expiry_type_date ON public.nifty_expiry_calendar USING btree (expiry_type, expiry_date);


--
-- Name: idx_nse_holidays_segment_date; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_nse_holidays_segment_date ON public.nse_holidays USING btree (segment, holiday_date);


--
-- Name: idx_options_expiry; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_options_expiry ON public.nifty_options_data USING btree (expiry_date);


--
-- Name: idx_options_expiry_strike; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_options_expiry_strike ON public.nifty_options_data USING btree (expiry_date, strike);


--
-- Name: idx_options_strike; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_options_strike ON public.nifty_options_data USING btree (strike);


--
-- Name: idx_options_symbol; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_options_symbol ON public.nifty_options_data USING btree (symbol);


--
-- Name: idx_options_timestamp; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_options_timestamp ON public.nifty_options_data USING btree ("timestamp");


--
-- Name: ix_instruments_strategy_contract; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_instruments_strategy_contract ON public.instruments USING btree (underlying_symbol, instrument_type, expiry, strike);


--
-- Name: ix_nifty_expiry_calendar_strategy; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_nifty_expiry_calendar_strategy ON public.nifty_expiry_calendar USING btree (underlying, expiry_type, expiry_date);


--
-- Name: candles_1min_2026_02_pkey; Type: INDEX ATTACH; Schema: public; Owner: postgres
--

ALTER INDEX public.candles_1min_pkey ATTACH PARTITION public.candles_1min_2026_02_pkey;


--
-- Name: candles_1min_2026_03_pkey; Type: INDEX ATTACH; Schema: public; Owner: postgres
--

ALTER INDEX public.candles_1min_pkey ATTACH PARTITION public.candles_1min_2026_03_pkey;


--
-- Name: candles_1min_2026_04_pkey; Type: INDEX ATTACH; Schema: public; Owner: postgres
--

ALTER INDEX public.candles_1min_pkey ATTACH PARTITION public.candles_1min_2026_04_pkey;


--
-- Name: candles_1min_2026_05_pkey; Type: INDEX ATTACH; Schema: public; Owner: postgres
--

ALTER INDEX public.candles_1min_pkey ATTACH PARTITION public.candles_1min_2026_05_pkey;


--
-- Name: candles_1min_2026_06_pkey; Type: INDEX ATTACH; Schema: public; Owner: postgres
--

ALTER INDEX public.candles_1min_pkey ATTACH PARTITION public.candles_1min_2026_06_pkey;


--
-- Name: candles_1min_2026_07_pkey; Type: INDEX ATTACH; Schema: public; Owner: postgres
--

ALTER INDEX public.candles_1min_pkey ATTACH PARTITION public.candles_1min_2026_07_pkey;


--
-- Name: candles_1min_2026_08_pkey; Type: INDEX ATTACH; Schema: public; Owner: postgres
--

ALTER INDEX public.candles_1min_pkey ATTACH PARTITION public.candles_1min_2026_08_pkey;


--
-- Name: candles_1min_2026_09_pkey; Type: INDEX ATTACH; Schema: public; Owner: postgres
--

ALTER INDEX public.candles_1min_pkey ATTACH PARTITION public.candles_1min_2026_09_pkey;


--
-- Name: candles_1min candles_1min_instrument_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE public.candles_1min
    ADD CONSTRAINT candles_1min_instrument_id_fkey FOREIGN KEY (instrument_id) REFERENCES public.instruments(id);


--
-- Name: ingestion_progress ingestion_progress_instrument_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ingestion_progress
    ADD CONSTRAINT ingestion_progress_instrument_id_fkey FOREIGN KEY (instrument_id) REFERENCES public.instruments(id);


--
-- Name: instruments instruments_exchange_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.instruments
    ADD CONSTRAINT instruments_exchange_id_fkey FOREIGN KEY (exchange_id) REFERENCES public.exchanges(id);


--
-- PostgreSQL database dump complete
--

\unrestrict 2L0lN0qX9ydMVMMsQJmGZw75brZB0mInJAUBrhFG0BkrMDbfHaKHGkoNBcwJfb4

