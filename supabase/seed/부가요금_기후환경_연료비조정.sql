-- 기후환경요금 · 연료비조정단가 시계열
-- source_type 이 '보도' 인 값은 한전 공식 고시로 확인되지 않았다.
insert into pricing.electricity_surcharge
  (kind, effective_from, period_label, won_per_kwh, source, source_type, confidence, note)
values
  ('기후환경요금', '2021-01-01', NULL, 5.3, '2021-01-01 시행 전기요금표(종합)', '요금표', 'high', '요금표에 ''기후환경요금단가 : 5.3원/kWh (21년 1월 기준)'' 으로 명시. 레포의 sources/electricity/2021-01-01_종합.pdf 에서 직접 확인.'),
  ('기후환경요금', '2025-01-01', NULL, 9.0, '언론 보도 (2021년 5.3원 → 2025년 9.0원, 약 70% 인상)', '보도', 'medium', '2025~2026년에 9.0원이 적용 중이라는 보도에 근거. 정확히 언제 9.0원이 되었는지는 확인하지 못했으므로 시행일 2025-01-01 은 추정이다. 2022~2024년 값도 확인하지 못했다. 같은 보도가 2021년 값을 5.3원으로 적어 요금표 원본과 일치하는 점은 신뢰도를 높인다.'),
  ('연료비조정단가', '2025-10-01', '2025년 4분기', 5.0, '언론 보도 (2026년 1분기 동결 기사에서 ''2025년 4분기와 동일'' 로 언급)', '보도', 'medium', NULL),
  ('연료비조정단가', '2026-01-01', '2026년 1분기', 5.0, '언론 보도 (한전, 2026년 1분기 연료비조정단가 kWh당 5원 유지 발표)', '보도', 'medium', NULL),
  ('연료비조정단가', '2026-07-01', '2026년 3분기', 5.0, '언론 보도 (4분기 동결 기사에서 ''3분기에도 +5원'' 으로 언급)', '보도', 'medium', NULL),
  ('연료비조정단가', '2026-10-01', '2026년 4분기', 5.0, '언론 보도 (한전 2026-09-21 발표, 3분기와 동일한 +5원 유지)', '보도', 'medium', NULL)
on conflict (kind, effective_from) do update set
  won_per_kwh = excluded.won_per_kwh,
  source = excluded.source,
  source_type = excluded.source_type,
  confidence = excluded.confidence,
  note = excluded.note;
