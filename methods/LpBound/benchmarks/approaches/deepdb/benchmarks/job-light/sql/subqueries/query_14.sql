select COUNT(*) from title t, movie_info mi where t.production_year > 1990 and t.id=mi.movie_id;
select COUNT(*) from title t, movie_companies mc where t.production_year > 1990 and mc.company_type_id = 2 and t.id=mc.movie_id;
select COUNT(*) from title t, movie_info mi, movie_companies mc where t.production_year > 1990 and mc.company_type_id = 2 and t.id=mc.movie_id and t.id=mi.movie_id;
