select COUNT(*) from title t, movie_keyword mk where mk.keyword_id = 398 and t.id=mk.movie_id;
select COUNT(*) from title t, movie_companies mc where mc.company_type_id = 2 and t.id=mc.movie_id;
select COUNT(*) from title t, movie_keyword mk, movie_companies mc where mk.keyword_id = 398 and t.id=mk.movie_id and mc.company_type_id = 2 and t.id=mc.movie_id;
