select COUNT(*) from title t, movie_info mi where mi.info_type_id = 3 and t.id=mi.movie_id;
select COUNT(*) from title t, movie_info_idx mi_idx where mi_idx.info_type_id = 100 and t.id=mi_idx.movie_id;
select COUNT(*) from title t, cast_info ci where t.id=ci.movie_id;
select COUNT(*) from title t, movie_info mi, movie_info_idx mi_idx where mi_idx.info_type_id = 100 and t.id=mi_idx.movie_id and mi.info_type_id = 3 and t.id=mi.movie_id;
select COUNT(*) from title t, movie_info mi, cast_info ci where t.id=ci.movie_id and mi.info_type_id = 3 and t.id=mi.movie_id;
select COUNT(*) from title t, movie_info_idx mi_idx, cast_info ci where mi_idx.info_type_id = 100 and t.id=mi_idx.movie_id and t.id=ci.movie_id;
select COUNT(*) from title t, movie_info mi, movie_info_idx mi_idx, cast_info ci where mi_idx.info_type_id = 100 and t.id=mi_idx.movie_id and t.id=ci.movie_id and mi.info_type_id = 3 and t.id=mi.movie_id;
