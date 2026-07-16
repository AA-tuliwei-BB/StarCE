select COUNT(*) from title t, movie_companies mc where t.id=mc.movie_id;
select COUNT(*) from title t, movie_keyword mk where mk.keyword_id = 117 and t.id=mk.movie_id;
select COUNT(*) from title t, movie_companies mc, movie_keyword mk where mk.keyword_id = 117 and t.id=mk.movie_id and t.id=mc.movie_id;
