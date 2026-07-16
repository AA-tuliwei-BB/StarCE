select COUNT(*) from title t, movie_info mi where mi.info_type_id = 105 and t.id=mi.movie_id;
select COUNT(*) from title t, movie_info_idx mi_idx where mi_idx.info_type_id = 113 and t.id=mi_idx.movie_id;
select COUNT(*) from title t, movie_companies mc where t.id=mc.movie_id;
select COUNT(*) from title t, movie_info mi, movie_info_idx mi_idx where mi_idx.info_type_id = 113 and t.id=mi_idx.movie_id and mi.info_type_id = 105 and t.id=mi.movie_id;
select COUNT(*) from title t, movie_info mi, movie_companies mc where t.id=mc.movie_id and mi.info_type_id = 105 and t.id=mi.movie_id;
select COUNT(*) from title t, movie_info_idx mi_idx, movie_companies mc where mi_idx.info_type_id = 113 and t.id=mi_idx.movie_id and t.id=mc.movie_id;
select COUNT(*) from title t, movie_info mi, movie_info_idx mi_idx, movie_companies mc where mi_idx.info_type_id = 113 and t.id=mi_idx.movie_id and t.id=mc.movie_id and mi.info_type_id = 105 and t.id=mi.movie_id;
