select COUNT(*) from title t, movie_companies mc where mc.company_type_id = 2 and t.id=mc.movie_id;
select COUNT(*) from title t, movie_info_idx mi_idx where mi_idx.info_type_id = 112 and t.id=mi_idx.movie_id;
select COUNT(*) from title t, movie_companies mc, movie_info_idx mi_idx where mi_idx.info_type_id = 112 and t.id=mi_idx.movie_id and mc.company_type_id = 2 and t.id=mc.movie_id;
