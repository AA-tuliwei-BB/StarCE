select COUNT(*) from title t, movie_companies mc where t.production_year > 1990 and t.id=mc.movie_id;
select COUNT(*) from title t, cast_info ci where t.production_year > 1990 and t.id=ci.movie_id;
select COUNT(*) from title t, movie_companies mc, cast_info ci where t.production_year > 1990 and t.id=ci.movie_id and t.id=mc.movie_id;
