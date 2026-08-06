select COUNT(*) from title t, movie_info mi where t.production_year > 2000 and mi.info_type_id = 16 and t.id=mi.movie_id;
select COUNT(*) from title t, movie_companies mc where t.production_year > 2000 and t.id=mc.movie_id;
select COUNT(*) from title t, cast_info ci where t.production_year > 2000 and ci.role_id = 2 and t.id=ci.movie_id;
select COUNT(*) from title t, movie_info mi, movie_companies mc where t.production_year > 2000 and t.id=mc.movie_id and mi.info_type_id = 16 and t.id=mi.movie_id;
select COUNT(*) from title t, movie_info mi, cast_info ci where t.production_year > 2000 and ci.role_id = 2 and t.id=ci.movie_id and mi.info_type_id = 16 and t.id=mi.movie_id;
select COUNT(*) from title t, movie_companies mc, cast_info ci where t.production_year > 2000 and t.id=mc.movie_id and ci.role_id = 2 and t.id=ci.movie_id;
select COUNT(*) from title t, movie_info mi, movie_companies mc, cast_info ci where t.production_year > 2000 and t.id=mc.movie_id and ci.role_id = 2 and t.id=ci.movie_id and mi.info_type_id = 16 and t.id=mi.movie_id;
