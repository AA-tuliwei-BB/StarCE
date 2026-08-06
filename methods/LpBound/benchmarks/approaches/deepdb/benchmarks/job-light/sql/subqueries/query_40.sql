select COUNT(*) from title t, movie_info mi where t.production_year > 2005 and mi.info_type_id = 8 and t.id=mi.movie_id;
select COUNT(*) from title t, movie_keyword mk where t.production_year > 2005 and t.id=mk.movie_id;
select COUNT(*) from title t, movie_info_idx mi_idx where t.production_year > 2005 and mi_idx.info_type_id = 101 and t.id=mi_idx.movie_id;
select COUNT(*) from title t, movie_info mi, movie_keyword mk where t.production_year > 2005 and t.id=mk.movie_id and mi.info_type_id = 8 and t.id=mi.movie_id;
select COUNT(*) from title t, movie_info mi, movie_info_idx mi_idx where t.production_year > 2005 and mi_idx.info_type_id = 101 and t.id=mi_idx.movie_id and mi.info_type_id = 8 and t.id=mi.movie_id;
select COUNT(*) from title t, movie_keyword mk, movie_info_idx mi_idx where t.production_year > 2005 and mi_idx.info_type_id = 101 and t.id=mi_idx.movie_id and t.id=mk.movie_id;
select COUNT(*) from title t, movie_info mi, movie_keyword mk, movie_info_idx mi_idx where t.production_year > 2005 and mi_idx.info_type_id = 101 and t.id=mi_idx.movie_id and t.id=mk.movie_id and mi.info_type_id = 8 and t.id=mi.movie_id;
