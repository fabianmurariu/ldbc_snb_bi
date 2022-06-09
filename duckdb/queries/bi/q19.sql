DROP TABLE IF EXISTS Message;
DROP TABLE IF EXISTS interactions;
DROP TABLE IF EXISTS weights;
DROP TABLE IF EXISTS PersonInteractions;

pragma verify_parallelism;

CREATE TEMP TABLE Message as (SELECT p.id as messageid, NULL as ParentMessageId, p.CreatorPersonId
     FROM Post p
     UNION ALL
     SELECT c.id                                    as messageid,
            coalesce(ParentPostId, ParentCommentId) as ParentMessageId,
            c.CreatorPersonid
     FROM comment c);


CREATE TEMP TABLE interactions as (select least(m1.creatorpersonid, m2.creatorpersonid) as src,
                                         greatest(m1.creatorpersonid, m2.creatorpersonid) as dst,
                                         count(*) as c
                                  from Person_knows_person pp, Message m1, Message m2
                                  where pp.person1id = m1.creatorpersonid and pp.person2id = m2.creatorpersonid and m1.parentmessageid = m2.messageid and m1.creatorpersonid <> m2.creatorpersonid
                                  group by src, dst
                                  order by src, dst);

CREATE TEMP TABLE weights as (select src as person1id, dst as person2id, weight from (
                            select src, dst, 1.0::double precision / c as weight from interactions
                            union all
                            select dst, src, 1.0::double precision / c as weight from interactions)
                        order by src, dst);

-- PRECOMPUTE
CREATE TEMP TABLE PersonInteractions AS (SELECT DISTINCT r.Person1id as id, p.locationcityid
                                    FROM ((SELECT Person1id
                                           FROM weights)
                                          UNION ALL
                                          (SELECT Person2id AS Person1id
                                           FROM weights)) r
                                    JOIN person p on p.id = r.Person1id
                                    ORDER BY id);

-- CSR CREATION
SELECT DISTINCT CREATE_CSR(
               0,
               v.vcount,
               r.ecount,
               r.src,
               r.dst,
               r.weight
           )
FROM (SELECT count(p.id) as vcount FROM PersonInteractions p) v,
     (SELECT src.rowid as src, dst.rowid as dst, t.weight as weight, count(src.rowid) OVER (ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) as ecount
      FROM weights t
           JOIN PersonInteractions src ON t.Person1id = src.id
           JOIN PersonInteractions dst ON t.Person2id = dst.id
      order by src.rowid, dst.rowid) r;


create temp table results
(
    Person1id bigint,
    city1id bigint,
    Person2id bigint,
    city2id bigint,
    weight double
);

create temp table all_options
(
  Person1id bigint,
  Person1rowid bigint,
  City1id bigint,
  Person2id bigint,
  Person2rowid bigint,
  City2id bigint
);

-- PARAMS
INSERT INTO all_options (SELECT s.id AS person1id, s.rowid as person1rowid, s.LocationCityId AS City1id, s2.id AS person2id, s2.rowid as person2rowid, s2.LocationCityId as City2id FROM
                (SELECT pi.id, pi.rowid, pi.locationcityid FROM personinteractions pi WHERE pi.locationcityid = :city1id) s,
                (SELECT pi.id, pi.rowid, pi.locationcityid FROM personinteractions pi WHERE pi.locationcityid = :city2id) s2
);

-- DEBUG
select count(*) as parameter_timing from all_options;


-- PATH
INSERT INTO results (SELECT p.person1id, p.city1id, p.person2id, p.city2id, cheapest_path(0, (select count(*) from personinteractions), p.person1rowid, p.person2rowid) as weight from all_options p);

pragma delete_csr=0;

-- RESULTS
WITH agg AS (SELECT min(weight) AS min_weight, city1id, city2id
          FROM results
          GROUP BY city1id, city2id
          )
SELECT person1id,
person2id,
weight AS totalWeight,
results.city1id,
results.city2id
FROM results, agg
WHERE results.weight BETWEEN agg.min_weight - 0.00001 AND agg.min_weight + 0.00001 AND
      results.city1id = agg.city1id AND
      results.city2id = agg.city2id;
-- ORDER BY totalWeight ASC, person1id ASC, person2id ASC;

