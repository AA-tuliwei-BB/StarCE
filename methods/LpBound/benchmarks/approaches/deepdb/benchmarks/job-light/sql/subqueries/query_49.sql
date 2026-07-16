select COUNT(*) from title t, movie_info mi where mi.info_type_id = 16 and t.id=mi.movie_id;
select COUNT(*) from title t, movie_companies mc where t.id=mc.movie_id;
select COUNT(*) from title t, cast_info ci where ci.role_id = 2 and t.id=ci.movie_id;
select COUNT(*) from title t, movie_info mi, movie_companies mc where t.id=mc.movie_id and mi.info_type_id = 16 and t.id=mi.movie_id;
select COUNT(*) from title t, movie_info mi, cast_info ci where ci.role_id = 2 and t.id=ci.movie_id and mi.info_type_id = 16 and t.id=mi.movie_id;
select COUNT(*) from title t, movie_companies mc, cast_info ci where t.id=mc.movie_id and ci.role_id = 2 and t.id=ci.movie_id;
select COUNT(*) from title t, movie_info mi, movie_companies mc, cast_info ci where t.id=mc.movie_id and ci.role_id = 2 and t.id=ci.movie_id and mi.info_type_id = 16 and t.id=mi.movie_id;
