select COUNT(*) from title t, movie_keyword mk where t.production_year > 1950 and t.id=mk.movie_id;
select COUNT(*) from title t, movie_companies mc where t.production_year > 1950 and t.id=mc.movie_id;
select COUNT(*) from title t, movie_keyword mk, movie_companies mc where t.production_year > 1950 and t.id=mk.movie_id and t.id=mc.movie_id;
