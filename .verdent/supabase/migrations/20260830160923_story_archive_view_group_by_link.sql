-- Fold on the story's link (falling back to the headline when a feed gives no
-- URL) so a story seen both before and after provenance capture began is one
-- row, not two. headline/source_url collapse with min() for the same reason.
create or replace view public.story_archive
with (security_invoker = true) as
select
  n.section,
  n.outlet as source,
  min(n.headline) as headline,
  coalesce(nullif(n.url,''), n.headline) as link,
  min(n.source_url) as source_url,
  min(r.edition_date) as first_seen,
  max(r.edition_date) as last_seen,
  count(distinct n.run_id)::int as editions,
  min(n.published_at) as published_at
from public.news n
join public.digest_runs r on r.run_id = n.run_id
where r.edition_date >= (current_date - interval '30 days')
group by n.section, n.outlet, coalesce(nullif(n.url,''), n.headline)

union all

select
  'capital raises',
  c.region,
  min(c.headline),
  coalesce(nullif(c.url,''), c.headline),
  min(c.source_url),
  min(r.edition_date),
  max(r.edition_date),
  count(distinct c.run_id)::int,
  min(c.published_at)
from public.capital_raises c
join public.digest_runs r on r.run_id = c.run_id
where r.edition_date >= (current_date - interval '30 days')
group by c.region, coalesce(nullif(c.url,''), c.headline);

grant select on public.story_archive to anon, authenticated;