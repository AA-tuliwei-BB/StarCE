select COUNT(*) from title t, movie_info mi where t.production_year > 1990 and mi.info_type_id = 16 and t.id=mi.movie_id;
select COUNT(*) from title t, movie_keyword mk where t.production_year > 1990 and t.id=mk.movie_id;
select COUNT(*) from title t, movie_companies mc where t.production_year > 1990 and t.id=mc.movie_id;
select COUNT(*) from title t, movie_info mi, movie_keyword mk where t.production_year > 1990 and t.id=mk.movie_id and mi.info_type_id = 16 and t.id=mi.movie_id;
select COUNT(*) from title t, movie_info mi, movie_companies mc where t.production_year > 1990 and t.id=mc.movie_id and mi.info_type_id = 16 and t.id=mi.movie_id;
select COUNT(*) from title t, movie_keyword mk, movie_companies mc where t.production_year > 1990 and t.id=mc.movie_id and t.id=mk.movie_id;
select COUNT(*) from title t, movie_info mi, movie_keyword mk, movie_companies mc where t.production_year > 1990 and t.id=mc.movie_id and t.id=mk.movie_id and mi.info_type_id = 16 and t.id=mi.movie_id;
