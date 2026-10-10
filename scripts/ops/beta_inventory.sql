-- D4 Beta-Übergang: schreibfreie Inventur der Nutzung kostenintensiver Funktionen.
--
-- Nur Zähler je Konto, Konten ausschließlich als Kurz-Hash (Salt pro Lauf, nicht
-- umkehrbar, zwischen Läufen nicht korrelierbar). Keine E-Mail, kein Inhalt.
-- Läuft in einer read-only-Transaktion und ändert nichts.
--
--   psql -v salt="$(openssl rand -hex 8)" -f scripts/ops/beta_inventory.sql
--
-- Das Gegenstück im Anwendungscode ist `python -m numra_api.cli beta inventory`
-- (HMAC-Pseudonyme mit dem Session-Secret, identische Zählweise); dieses Skript
-- funktioniert auch VOR dem Deploy, weil es nur bestehende Tabellen liest.
BEGIN READ ONLY;

WITH reports AS (
  SELECT user_id, count(*) AS n FROM reports GROUP BY user_id
), analyses AS (
  SELECT requested_by_user_id AS user_id, count(*) AS n FROM analysis_jobs GROUP BY 1
), patterns AS (
  SELECT user_id, count(*) AS n FROM pattern_analyses GROUP BY user_id
), copilot AS (
  SELECT author_user_id AS user_id, count(*) AS n
  FROM chat_messages WHERE role = 'USER' AND author_user_id IS NOT NULL GROUP BY 1
), used AS (
  SELECT user_id FROM reports UNION SELECT user_id FROM analyses
  UNION SELECT user_id FROM patterns UNION SELECT user_id FROM copilot
)
SELECT substr(md5(u.user_id::text || :'salt'), 1, 8) AS konto,
       coalesce(r.n, 0) AS reports,
       coalesce(a.n, 0) AS analysen,
       coalesce(p.n, 0) AS muster,
       coalesce(c.n, 0) AS copilot_nachrichten,
       usr.is_active AS aktiv,
       (g.user_id IS NOT NULL) AS freigeschaltet
FROM used u
JOIN users usr ON usr.id = u.user_id
LEFT JOIN reports r ON r.user_id = u.user_id
LEFT JOIN analyses a ON a.user_id = u.user_id
LEFT JOIN patterns p ON p.user_id = u.user_id
LEFT JOIN copilot c ON c.user_id = u.user_id
LEFT JOIN entitlement_assignments g ON g.user_id = u.user_id
ORDER BY (coalesce(r.n, 0) + coalesce(a.n, 0) + coalesce(p.n, 0) + coalesce(c.n, 0)) DESC, konto;

SELECT (SELECT count(*) FROM users) AS konten_gesamt,
       (SELECT count(*) FROM users WHERE is_active) AS konten_aktiv,
       (SELECT count(*) FROM entitlement_assignments) AS beta_freigaben;

ROLLBACK;
