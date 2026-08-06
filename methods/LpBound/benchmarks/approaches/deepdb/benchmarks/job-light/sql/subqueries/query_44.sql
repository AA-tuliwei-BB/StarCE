select COUNT(*) from title t, cast_info ci where t.id=ci.movie_id;
select COUNT(*) from title t, movie_keyword mk where mk.keyword_id = 117 and t.id=mk.movie_id;
select COUNT(*) from title t, movie_companies mc where t.id=mc.movie_id;
select COUNT(*) from title t, cast_info ci, movie_keyword mk where t.id=ci.movie_id and mk.keyword_id = 117 and t.id=mk.movie_id;
select COUNT(*) from title t, cast_info ci, movie_companies mc where t.id=ci.movie_id and t.id=mc.movie_id;
select COUNT(*) from title t, movie_keyword mk, movie_companies mc where t.id=mc.movie_id and mk.keyword_id = 117 and t.id=mk.movie_id;
select COUNT(*) from title t, cast_info ci, movie_keyword mk, movie_companies mc where t.id=ci.movie_id and t.id=mc.movie_id and mk.keyword_id = 117 and t.id=mk.movie_id;
