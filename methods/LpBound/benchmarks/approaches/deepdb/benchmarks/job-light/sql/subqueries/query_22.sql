select COUNT(*) from title t, cast_info ci where t.production_year > 1980 and t.production_year < 2010 and t.id=ci.movie_id;
