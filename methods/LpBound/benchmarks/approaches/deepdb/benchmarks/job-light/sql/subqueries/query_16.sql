select COUNT(*) from title t, movie_keyword mk where t.production_year > 2014 and t.id=mk.movie_id;
select COUNT(*) from title t, cast_info ci where t.production_year > 2014 and t.id=ci.movie_id;
select COUNT(*) from title t, movie_keyword mk, cast_info ci where t.production_year > 2014 and t.id=ci.movie_id and t.id=mk.movie_id;
