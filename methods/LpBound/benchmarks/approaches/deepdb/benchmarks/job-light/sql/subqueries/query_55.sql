select COUNT(*) from title t, movie_keyword mk where t.production_year > 1950 and t.production_year < 2010 and mk.keyword_id = 398 and t.id=mk.movie_id;
select COUNT(*) from title t, movie_companies mc where t.production_year > 1950 and t.production_year < 2010 and mc.company_type_id = 2 and t.id=mc.movie_id;
select COUNT(*) from title t, movie_info mi where t.production_year > 1950 and t.production_year < 2010 and t.id=mi.movie_id;
select COUNT(*) from title t, movie_keyword mk, movie_companies mc where t.production_year > 1950 and t.production_year < 2010 and mk.keyword_id = 398 and t.id=mk.movie_id and mc.company_type_id = 2 and t.id=mc.movie_id;
select COUNT(*) from title t, movie_keyword mk, movie_info mi where t.production_year > 1950 and t.production_year < 2010 and t.id=mi.movie_id and mk.keyword_id = 398 and t.id=mk.movie_id;
select COUNT(*) from title t, movie_companies mc, movie_info mi where t.production_year > 1950 and t.production_year < 2010 and t.id=mi.movie_id and mc.company_type_id = 2 and t.id=mc.movie_id;
select COUNT(*) from title t, movie_keyword mk, movie_companies mc, movie_info mi where t.production_year > 1950 and t.production_year < 2010 and t.id=mi.movie_id and mk.keyword_id = 398 and t.id=mk.movie_id and mc.company_type_id = 2 and t.id=mc.movie_id;
