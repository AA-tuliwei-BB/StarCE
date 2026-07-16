select COUNT(*) from title t, movie_info mi where t.production_year > 2010 and t.id=mi.movie_id;
select COUNT(*) from title t, movie_keyword mk where t.production_year > 2010 and t.id=mk.movie_id;
select COUNT(*) from title t, movie_info mi, movie_keyword mk where t.production_year > 2010 and t.id=mk.movie_id and t.id=mi.movie_id;
