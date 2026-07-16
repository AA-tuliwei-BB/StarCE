select COUNT(*) from title t, movie_info mi where t.production_year > 2008 and t.production_year < 2014 and mi.info_type_id = 3 and t.id=mi.movie_id;
select COUNT(*) from title t, movie_info_idx mi_idx where t.production_year > 2008 and t.production_year < 2014 and mi_idx.info_type_id = 101 and t.id=mi_idx.movie_id;
select COUNT(*) from title t, cast_info ci where t.production_year > 2008 and t.production_year < 2014 and t.id=ci.movie_id;
select COUNT(*) from title t, movie_info mi, movie_info_idx mi_idx where t.production_year > 2008 and t.production_year < 2014 and mi_idx.info_type_id = 101 and t.id=mi_idx.movie_id and mi.info_type_id = 3 and t.id=mi.movie_id;
select COUNT(*) from title t, movie_info mi, cast_info ci where t.production_year > 2008 and t.production_year < 2014 and t.id=ci.movie_id and mi.info_type_id = 3 and t.id=mi.movie_id;
select COUNT(*) from title t, movie_info_idx mi_idx, cast_info ci where t.production_year > 2008 and t.production_year < 2014 and mi_idx.info_type_id = 101 and t.id=mi_idx.movie_id and t.id=ci.movie_id;
select COUNT(*) from title t, movie_info mi, movie_info_idx mi_idx, cast_info ci where t.production_year > 2008 and t.production_year < 2014 and mi_idx.info_type_id = 101 and t.id=mi_idx.movie_id and t.id=ci.movie_id and mi.info_type_id = 3 and t.id=mi.movie_id;
