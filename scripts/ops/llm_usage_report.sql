-- D4: schreibfreie Aggregation von llm_generations (nur Zaehler/Summen, keine Inhalte).
-- NULL-Tokens werden NIE als 0 gewertet: Summen nur ueber vorhandene Werte, NULL-Anteil getrennt.
BEGIN READ ONLY;

SELECT count(*) AS zeilen, min(created_at) AS von, max(created_at) AS bis FROM llm_generations;

SELECT source, provider, model, status,
       count(*) AS n,
       count(*) FILTER (WHERE prompt_tokens IS NULL) AS n_prompt_null,
       count(*) FILTER (WHERE completion_tokens IS NULL) AS n_compl_null,
       sum(prompt_tokens) AS sum_prompt_nicht_null,
       sum(completion_tokens) AS sum_compl_nicht_null,
       round(avg(latency_ms)) AS avg_ms,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY latency_ms) AS p50_ms,
       percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95_ms,
       max(latency_ms) AS max_ms
FROM llm_generations
GROUP BY 1, 2, 3, 4
ORDER BY 1, 2, 3, 4;

SELECT source,
       count(*) AS aufrufe,
       count(*) FILTER (WHERE status = 'ok') AS ok,
       count(*) FILTER (WHERE status <> 'ok') AS nicht_ok,
       count(DISTINCT coalesce(report_job_id, analysis_job_id, chat_message_id)) AS einheiten
FROM llm_generations
GROUP BY 1
ORDER BY 1;

SELECT source, round(avg(c)::numeric, 1) AS avg_aufrufe_je_einheit, max(c) AS max_aufrufe_je_einheit
FROM (
  SELECT source, coalesce(report_job_id, analysis_job_id, chat_message_id) AS u, count(*) AS c
  FROM llm_generations GROUP BY 1, 2
) t
GROUP BY 1
ORDER BY 1;

SELECT (SELECT count(*) FROM reports) AS reports,
       (SELECT count(*) FROM report_jobs) AS report_jobs,
       (SELECT count(*) FROM report_jobs WHERE status = 'FAILED') AS report_jobs_failed,
       (SELECT count(*) FROM analysis_jobs) AS analysis_jobs,
       (SELECT count(*) FROM analysis_jobs WHERE status = 'FAILED') AS analysis_jobs_failed,
       (SELECT count(*) FROM chat_messages WHERE role = 'USER') AS chat_user_msgs,
       (SELECT count(*) FROM chat_messages WHERE role = 'ASSISTANT' AND status = 'FAILED') AS chat_failed;


-- Jobdauer und Fehler je Funktion (unabhaengig von llm_generations)
SELECT 'report' AS funktion, status, count(*) AS n,
       round(avg(extract(epoch FROM (updated_at - created_at)))) AS avg_s,
       round(max(extract(epoch FROM (updated_at - created_at)))) AS max_s,
       round(avg(attempt_count), 1) AS avg_versuche, max(attempt_count) AS max_versuche
FROM report_jobs GROUP BY status
UNION ALL
SELECT 'analysis', status, count(*),
       round(avg(extract(epoch FROM (updated_at - created_at)))),
       round(max(extract(epoch FROM (updated_at - created_at)))),
       round(avg(attempt_count), 1), max(attempt_count)
FROM analysis_jobs GROUP BY status
ORDER BY 1, 2;
SELECT error_code, count(*) FROM report_jobs WHERE status = 'FAILED' GROUP BY 1 ORDER BY 2 DESC;
SELECT date_trunc('day', created_at) AS tag, count(*) AS report_jobs FROM report_jobs GROUP BY 1 ORDER BY 1;
ROLLBACK;
