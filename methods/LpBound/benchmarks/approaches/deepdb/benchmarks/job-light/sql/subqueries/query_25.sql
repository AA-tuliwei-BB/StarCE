select COUNT(*) from title t, cast_info ci where ci.role_id = 7 and t.id=ci.movie_id;
select COUNT(*) from title t, movie_companies mc where t.id=mc.movie_id;
select COUNT(*) from title t, cast_info ci, movie_companies mc where ci.role_id = 7 and t.id=ci.movie_id and t.id=mc.movie_id;
