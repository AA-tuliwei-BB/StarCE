select COUNT(*) from title t, movie_info mi where t.kind_id = 1 and mi.info_type_id = 16 and t.id=mi.movie_id;
select COUNT(*) from title t, movie_companies mc where t.kind_id = 1 and mc.company_type_id = 2 and t.id=mc.movie_id;
select COUNT(*) from title t, movie_info_idx mi_idx where t.kind_id = 1 and mi_idx.info_type_id = 101 and t.id=mi_idx.movie_id;
select COUNT(*) from title t, movie_info mi, movie_companies mc where t.kind_id = 1 and mc.company_type_id = 2 and t.id=mc.movie_id and mi.info_type_id = 16 and t.id=mi.movie_id;
select COUNT(*) from title t, movie_info mi, movie_info_idx mi_idx where t.kind_id = 1 and mi_idx.info_type_id = 101 and t.id=mi_idx.movie_id and mi.info_type_id = 16 and t.id=mi.movie_id;
select COUNT(*) from title t, movie_companies mc, movie_info_idx mi_idx where t.kind_id = 1 and mi_idx.info_type_id = 101 and t.id=mi_idx.movie_id and mc.company_type_id = 2 and t.id=mc.movie_id;
select COUNT(*) from title t, movie_info mi, movie_companies mc, movie_info_idx mi_idx where t.kind_id = 1 and mi_idx.info_type_id = 101 and t.id=mi_idx.movie_id and mc.company_type_id = 2 and t.id=mc.movie_id and mi.info_type_id = 16 and t.id=mi.movie_id;
