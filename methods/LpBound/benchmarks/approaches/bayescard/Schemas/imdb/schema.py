from Schemas.graph_representation import SchemaGraph, Table


def gen_stats_schema(csv_path):
    
    schema = SchemaGraph()
    
    # badges
    schema.add_table(Table('badges', attributes=['id', 'user_id', 'date'],
                           csv_file_location=csv_path.format('badges'),
                           table_size=79851))
    
    # comments
    schema.add_table(Table('comments', attributes=['id', 'post_id', 'score', 'creation_date', 'user_id'],
                           csv_file_location=csv_path.format('comments'),
                           table_size=174305))
    
    # postHistory
    schema.add_table(Table('post_history', attributes=['id', 'post_history_type_id', 'post_id', 'creation_date', 'user_id'],
                           csv_file_location=csv_path.format('postHistory'),
                           table_size=303187))
    
    # postLinks
    schema.add_table(Table('post_links', attributes=['id', 'creation_date', 'post_id', 'related_post_id', 'link_type_id'],
                           csv_file_location=csv_path.format('postLinks'),
                           table_size=11102))
    
    # posts
    schema.add_table(Table('posts', attributes=['id', 'post_type_id', 'creation_date', 'score', 'view_count', 
                                                'owner_user_id', 'answer_count', 'comment_count', 'favorite_count', 'last_editor_user_id'],
                           csv_file_location=csv_path.format('posts'),
                           table_size=91976))
    
    # tags
    schema.add_table(Table('tags', attributes=['id', 'count', 'excerpt_post_id'],
                           csv_file_location=csv_path.format('tags'),
                           table_size=1032))
    
    # users
    schema.add_table(Table('users', attributes=['id', 'reputation', 'creation_date', 'views', 'up_votes', 'down_votes'],
                           csv_file_location=csv_path.format('users'),
                           table_size=40325))
    
    # votes
    schema.add_table(Table('votes', attributes=['id', 'post_id', 'vote_type_id', 'creation_date', 'user_id', 'bounty_amount'],
                           csv_file_location=csv_path.format('votes'),
                           table_size=328064))
    

    # relationships
    schema.add_relationship('badges', 'user_id', 'users', 'id')
    schema.add_relationship('comments', 'post_id', 'posts', 'id')
    
    schema.add_relationship('post_history', 'post_id', 'posts', 'id')
    schema.add_relationship('post_history', 'user_id', 'users', 'id')
    
    schema.add_relationship('post_links', 'post_id', 'posts', 'id')
    schema.add_relationship('post_links', 'related_post_id', 'posts', 'id')
    
    schema.add_relationship('posts', 'owner_user_id', 'users', 'id')
    
    schema.add_relationship('tags', 'excerpt_post_id', 'posts', 'id')
    
    schema.add_relationship('votes', 'post_id', 'posts', 'id')
    schema.add_relationship('votes', 'user_id', 'users', 'id')
    
    #schema.add_relationship('badges', 'user_id', 'posts', 'owner_user_id')
    
    
    return schema
    

def gen_job_light_imdb_schema(csv_path):
    """
    Just like the full IMDB schema but without tables that are not used in the job-light benchmark.
    """

    schema = SchemaGraph()

    # tables

    # title
    schema.add_table(Table('title', attributes=['id', 'title', 'imdb_index', 'kind_id', 'production_year', 'imdb_id',
                                                'phonetic_code', 'episode_of_id', 'season_nr', 'episode_nr',
                                                'series_years', 'md5sum'],
                           irrelevant_attributes=['episode_of_id', 'title', 'imdb_index', 'phonetic_code', 'season_nr',
                                                  'imdb_id', 'episode_nr', 'series_years', 'md5sum'],
                           no_compression=['kind_id'],
                           csv_file_location=csv_path.format('title'),
                           table_size=2528312))

    # movie_info_idx
    schema.add_table(Table('movie_info_idx', attributes=['id', 'movie_id', 'info_type_id', 'info', 'note'],
                           csv_file_location=csv_path.format('movie_info_idx'),
                           irrelevant_attributes=['info', 'note'],
                           no_compression=['info_type_id'],
                           table_size=1380035))

    # movie_info
    schema.add_table(Table('movie_info', attributes=['id', 'movie_id', 'info_type_id', 'info', 'note'],
                           csv_file_location=csv_path.format('movie_info'),
                           irrelevant_attributes=['info', 'note'],
                           no_compression=['info_type_id'],
                           table_size=14835720))

    # cast_info
    schema.add_table(Table('cast_info', attributes=['id', 'person_id', 'movie_id', 'person_role_id', 'note', 'nr_order',
                                                    'role_id'],
                           csv_file_location=csv_path.format('cast_info'),
                           irrelevant_attributes=['nr_order', 'note', 'person_id', 'person_role_id'],
                           no_compression=['role_id'],
                           table_size=36244344))

    # movie_keyword
    schema.add_table(Table('movie_keyword', attributes=['id', 'movie_id', 'keyword_id'],
                           csv_file_location=csv_path.format('movie_keyword'),
                           no_compression=['keyword_id'],
                           table_size=4523930))

    # movie_companies
    schema.add_table(Table('movie_companies', attributes=['id', 'movie_id', 'company_id', 'company_type_id', 'note'],
                           csv_file_location=csv_path.format('movie_companies'),
                           irrelevant_attributes=['note'],
                           no_compression=['company_id', 'company_type_id'],
                           table_size=2609129))
    
    # job join specific tables
    """
    # info_type
    schema.add_table(Table('info_type', attributes=['id', 'info'],
                           csv_file_location=csv_path.format('info_type'),
                           table_size=113))
    
    # company_type
    schema.add_table(Table('company_type', attributes=['id', 'kind'],
                           csv_file_location=csv_path.format('company_type'),
                           table_size=4))
    
    # complete_cast
    schema.add_table(Table('complete_cast', attributes=['id', 'movie_id', 'subject_id', 'status_id'],
                           csv_file_location=csv_path.format('complete_cast'),
                           table_size=135086))
    
    # comp_cast_type
    schema.add_table(Table('comp_cast_type', attributes=['id', 'kind'],
                           csv_file_location=csv_path.format('comp_cast_type'),
                           table_size=4))
    
    # char_name
    schema.add_table(Table('char_name', attributes=['id', 'name', 'imdb_index', 'imdb_id', 'name_pcode_nf',
                                                    'surname_pcode', 'md5sum'],
                           irrelevant_attributes=['imdb_index', 'imdb_id', 'name_pcode_nf', 'surname_pcode', 'md5sum'],
                           csv_file_location=csv_path.format('char_name'),
                           table_size=3140339))
    
    # company_name
    schema.add_table(Table('company_name', attributes=['id', 'name', 'country_code', 'imdb_id', 'name_pcode_nf',
                                                       'name_pcode_sf', 'md5sum'],
                           irrelevant_attributes=['country_code', 'imdb_id', 'name_pcode_nf', 'name_pcode_sf', 'md5sum'],
                           csv_file_location=csv_path.format('company_name'),
                           table_size=234997))
    """
    
    
    
    

    # relationships
    schema.add_relationship('movie_info_idx', 'movie_id', 'title', 'id')
    schema.add_relationship('movie_info', 'movie_id', 'title', 'id')
    schema.add_relationship('cast_info', 'movie_id', 'title', 'id')
    schema.add_relationship('movie_keyword', 'movie_id', 'title', 'id')
    schema.add_relationship('movie_companies', 'movie_id', 'title', 'id')
    
    # job join specific relationships    
    #schema.add_relationship('movie_info_idx', 'info_type_id', 'info_type', 'id')
    #schema.add_relationship('movie_companies', 'company_id', 'company_name', 'id')
    #schema.add_relationship('movie_companies', 'company_type_id', 'company_type', 'id')
    #schema.add_relationship('complete_cast', 'subject_id', 'comp_cast_type', 'id')
    #schema.add_relationship('complete_cast', 'status_id', 'comp_cast_type', 'id')
    #schema.add_relationship('cast_info', 'person_id', 'char_name', 'id')
    
    

    return schema


def gen_imdb_schema_old(csv_path):
    """
    Specifies full imdb schema. Also tables not in the job-light benchmark.
    """
    schema = SchemaGraph()

    # tables

    # title
    schema.add_table(Table('title', attributes=['id', 'title', 'imdb_index', 'kind_id', 'production_year', 'imdb_id',
                                                'phonetic_code', 'episode_of_id', 'season_nr', 'episode_nr',
                                                'series_years', 'md5sum'],
                           irrelevant_attributes=['episode_of_id', 'md5sum'],
                           csv_file_location=csv_path.format('title'),
                           table_size=2528312))

    # movie_info_idx
    schema.add_table(Table('movie_info_idx', attributes=['id', 'movie_id', 'info_type_id', 'info', 'note'],
                           csv_file_location=csv_path.format('movie_info_idx'),
                           table_size=1380035))

    # movie_info
    schema.add_table(Table('movie_info', attributes=['id', 'movie_id', 'info_type_id', 'info', 'note'],
                           csv_file_location=csv_path.format('movie_info'),
                           table_size=14835720))

    # info_type
    schema.add_table(Table('info_type', attributes=['id', 'info'],
                           csv_file_location=csv_path.format('info_type'),
                           table_size=113))

    # cast_info
    schema.add_table(Table('cast_info', attributes=['id', 'person_id', 'movie_id', 'person_role_id', 'note', 'nr_order',
                                                    'role_id'],
                           csv_file_location=csv_path.format('cast_info'),
                           table_size=36244344))

    # char_name
    schema.add_table(Table('char_name', attributes=['id', 'name', 'imdb_index', 'imdb_id', 'name_pcode_nf',
                                                    'surname_pcode', 'md5sum'],
                           csv_file_location=csv_path.format('char_name'),
                           table_size=3140339))

    # role_type
    schema.add_table(Table('role_type', attributes=['id', 'role'],
                           csv_file_location=csv_path.format('role_type'),
                           table_size=12))

    # complete_cast
    schema.add_table(Table('complete_cast', attributes=['id', 'movie_id', 'subject_id', 'status_id'],
                           csv_file_location=csv_path.format('complete_cast'),
                           table_size=135086))

    # comp_cast_type
    schema.add_table(Table('comp_cast_type', attributes=['id', 'kind'],
                           csv_file_location=csv_path.format('comp_cast_type'),
                           table_size=4))

    # name
    schema.add_table(Table('name', attributes=['id', 'name', 'imdb_index', 'imdb_id', 'gender', 'name_pcode_cf',
                                               'name_pcode_nf', 'surname_pcode', 'md5sum'],
                           irrelevant_attributes=['imdb_index', 'imdb_id', 'name_pcode_cf', 'name_pcode_nf', 'surname_pcode', 'md5sum'],
                           csv_file_location=csv_path.format('name'),
                           table_size=4167491))

    # aka_name
    schema.add_table(Table('aka_name', attributes=['id', 'person_id', 'name', 'imdb_index', 'name_pcode_cf',
                                                   'name_pcode_nf', 'surname_pcode', 'md5sum'],
                           csv_file_location=csv_path.format('aka_name'),
                           table_size=901343))

    # movie_link
    schema.add_table(Table('movie_link', attributes=['id', 'movie_id', 'linked_movie_id', 'link_type_id'],
                           csv_file_location=csv_path.format('movie_link'),
                           table_size=29997))

    # link_type
    schema.add_table(Table('link_type', attributes=['id', 'link'],
                           csv_file_location=csv_path.format('link_type'),
                           table_size=18))

    # movie_keyword
    schema.add_table(Table('movie_keyword', attributes=['id', 'movie_id', 'keyword_id'],
                           csv_file_location=csv_path.format('movie_keyword'),
                           table_size=4523930))

    # keyword
    schema.add_table(Table('keyword', attributes=['id', 'keyword', 'phonetic_code'],
                           csv_file_location=csv_path.format('keyword'),
                           table_size=134170))

    # person_info
    schema.add_table(Table('person_info', attributes=['id', 'person_id', 'info_type_id', 'info', 'note'],
                           csv_file_location=csv_path.format('person_info'),
                           irrelevant_attributes=['info', 'note'],
                           table_size=2963664))

    # movie_companies
    schema.add_table(Table('movie_companies', attributes=['id', 'movie_id', 'company_id', 'company_type_id', 'note'],
                           csv_file_location=csv_path.format('movie_companies'),
                           irrelevant_attributes=['note'],
                           no_compression=['company_id', 'company_type_id'],
                           table_size=2609129))

    # company_name
    schema.add_table(Table('company_name', attributes=['id', 'name', 'country_code', 'imdb_id', 'name_pcode_nf',
                                                       'name_pcode_sf', 'md5sum'],
                           irrelevant_attributes=['country_code', 'imdb_id', 'name_pcode_nf', 'name_pcode_sf', 'md5sum'],
                           csv_file_location=csv_path.format('company_name'),
                           table_size=234997))

    # company_type
    schema.add_table(Table('company_type', attributes=['id', 'kind'],
                           csv_file_location=csv_path.format('company_type'),
                           table_size=4))

    # aka_title
    schema.add_table(Table('aka_title', attributes=['id', 'movie_id', 'title', 'imdb_index', 'kind_id',
                                                    'production_year', 'phonetic_code', 'episode_of_id', 'season_nr',
                                                    'episode_nr', 'note', 'md5sum'],
                           irrelevant_attributes=['imdb_index', 'note', 'md5sum'],
                           csv_file_location=csv_path.format('aka_title'),
                           table_size=361472))

    # kind_type
    schema.add_table(Table('kind_type', attributes=['id', 'kind'],
                           csv_file_location=csv_path.format('kind_type'),
                           table_size=7))

    # relationships

    # title
    # omit self-join for now
    # schema.add_relationship('title', 'episode_of_id', 'title', 'id')
    schema.add_relationship('title', 'kind_id', 'kind_type', 'id')

    # movie_info_idx
    schema.add_relationship('movie_info_idx', 'info_type_id', 'info_type', 'id')
    schema.add_relationship('movie_info_idx', 'movie_id', 'title', 'id')

    # movie_info
    schema.add_relationship('movie_info', 'info_type_id', 'info_type', 'id')
    schema.add_relationship('movie_info', 'movie_id', 'title', 'id')

    # info_type, no relationships

    # cast_info
    schema.add_relationship('cast_info', 'movie_id', 'title', 'id')
    schema.add_relationship('cast_info', 'person_id', 'name', 'id')
    schema.add_relationship('cast_info', 'person_role_id', 'char_name', 'id')
    schema.add_relationship('cast_info', 'role_id', 'role_type', 'id')

    # char_name, no relationships

    # role_type, no relationships

    # complete_cast
    schema.add_relationship('complete_cast', 'movie_id', 'title', 'id')
    schema.add_relationship('complete_cast', 'status_id', 'comp_cast_type', 'id')
    schema.add_relationship('complete_cast', 'subject_id', 'comp_cast_type', 'id')

    # comp_cast_type, no relationships

    # name, no relationships

    # aka_name
    schema.add_relationship('aka_name', 'person_id', 'name', 'id')

    # movie_link, is empty
    schema.add_relationship('movie_link', 'link_type_id', 'link_type', 'id')
    schema.add_relationship('movie_link', 'linked_movie_id', 'title', 'id')
    schema.add_relationship('movie_link', 'movie_id', 'title', 'id')

    # link_type, no relationships

    # movie_keyword
    schema.add_relationship('movie_keyword', 'keyword_id', 'keyword', 'id')
    schema.add_relationship('movie_keyword', 'movie_id', 'title', 'id')

    # keyword, no relationships

    # person_info
    schema.add_relationship('person_info', 'info_type_id', 'info_type', 'id')
    schema.add_relationship('person_info', 'person_id', 'name', 'id')

    # movie_companies
    schema.add_relationship('movie_companies', 'company_id', 'company_name', 'id')
    schema.add_relationship('movie_companies', 'company_type_id', 'company_type', 'id')
    schema.add_relationship('movie_companies', 'movie_id', 'title', 'id')

    # company_name, no relationships

    # company_type, no relationships

    # aka_title
    schema.add_relationship('aka_title', 'movie_id', 'title', 'id')
    schema.add_relationship('aka_title', 'kind_id', 'kind_type', 'id')

    # kind_type, no relationships

    return schema


def gen_job_light_imdb_schema(csv_path):
    """
    Just like the full IMDB schema but without tables that are not used in the job-light benchmark.
    """

    schema = SchemaGraph()

    # tables

    # title
    schema.add_table(Table('title', attributes=['id', 'title', 'imdb_index', 'kind_id', 'production_year', 'imdb_id',
                                                'phonetic_code', 'episode_of_id', 'season_nr', 'episode_nr',
                                                'series_years', 'md5sum'],
                           irrelevant_attributes=['episode_of_id', 'title', 'imdb_index', 'phonetic_code', 'season_nr',
                                                  'imdb_id', 'episode_nr', 'series_years', 'md5sum'],
                           no_compression=['kind_id', "production_year"],
                           csv_file_location=csv_path.format('title'),
                           table_size=3486660))

    # movie_info_idx
    schema.add_table(Table('movie_info_idx', attributes=['id', 'movie_id', 'info_type_id', 'info', 'note'],
                           csv_file_location=csv_path.format('movie_info_idx'),
                           irrelevant_attributes=['info', 'note'],
                           no_compression=['info_type_id'],
                           table_size=3147110))

    # movie_info
    schema.add_table(Table('movie_info', attributes=['id', 'movie_id', 'info_type_id', 'info', 'note'],
                           csv_file_location=csv_path.format('movie_info'),
                           irrelevant_attributes=['info', 'note'],
                           no_compression=['info_type_id'],
                           table_size=24988000))

    # cast_info
    schema.add_table(Table('cast_info', attributes=['id', 'person_id', 'movie_id', 'person_role_id', 'note', 'nr_order',
                                                    'role_id'],
                           csv_file_location=csv_path.format('cast_info'),
                           irrelevant_attributes=['nr_order', 'note', 'person_id', 'person_role_id'],
                           no_compression=['role_id'],
                           table_size=63475800))

    # movie_keyword
    schema.add_table(Table('movie_keyword', attributes=['id', 'movie_id', 'keyword_id'],
                           csv_file_location=csv_path.format('movie_keyword'),
                           no_compression=['keyword_id'],
                           table_size=7522600))

    # movie_companies
    schema.add_table(Table('movie_companies', attributes=['id', 'movie_id', 'company_id', 'company_type_id', 'note'],
                           csv_file_location=csv_path.format('movie_companies'),
                           irrelevant_attributes=['note'],
                           no_compression=['company_id', 'company_type_id'],
                           table_size=4958300))

    # relationships
    schema.add_relationship('movie_info_idx', 'movie_id', 'title', 'id')
    schema.add_relationship('movie_info', 'movie_id', 'title', 'id')
    schema.add_relationship('cast_info', 'movie_id', 'title', 'id')
    schema.add_relationship('movie_keyword', 'movie_id', 'title', 'id')
    schema.add_relationship('movie_companies', 'movie_id', 'title', 'id')

    return schema


def gen_imdb_schema(csv_path):
    """
    Specifies full imdb schema. Also tables not in the job-light benchmark.
    """
    schema = SchemaGraph()

    # tables

    # title
    schema.add_table(Table('title', attributes=['id', 'title', 'imdb_index', 'kind_id', 'production_year', 'imdb_id',
                                                'phonetic_code', 'episode_of_id', 'season_nr', 'episode_nr',
                                                'series_years', 'md5sum'],
                           irrelevant_attributes=['episode_of_id', 'md5sum'],
                           csv_file_location=csv_path.format('title'),
                           table_size=2528312))

    # movie_info_idx
    schema.add_table(Table('movie_info_idx', attributes=['id', 'movie_id', 'info_type_id', 'info', 'note'],
                           csv_file_location=csv_path.format('movie_info_idx'),
                           table_size=1380035))

    # movie_info
    schema.add_table(Table('movie_info', attributes=['id', 'movie_id', 'info_type_id', 'info', 'note'],
                           csv_file_location=csv_path.format('movie_info'),
                           table_size=14835720))

    # info_type
    schema.add_table(Table('info_type', attributes=['id', 'info'],
                           csv_file_location=csv_path.format('info_type'),
                           table_size=113))

    # cast_info
    schema.add_table(Table('cast_info', attributes=['id', 'person_id', 'movie_id', 'person_role_id', 'note', 'nr_order',
                                                    'role_id'],
                           csv_file_location=csv_path.format('cast_info'),
                           table_size=36244344))

    # char_name
    schema.add_table(Table('char_name', attributes=['id', 'name', 'imdb_index', 'imdb_id', 'name_pcode_nf',
                                                    'surname_pcode', 'md5sum'],
                           csv_file_location=csv_path.format('char_name'),
                           table_size=3140339))

    # role_type
    schema.add_table(Table('role_type', attributes=['id', 'role'],
                           csv_file_location=csv_path.format('role_type'),
                           table_size=12))

    # complete_cast
    schema.add_table(Table('complete_cast', attributes=['id', 'movie_id', 'subject_id', 'status_id'],
                           csv_file_location=csv_path.format('complete_cast'),
                           table_size=135086))

    # comp_cast_type
    schema.add_table(Table('comp_cast_type', attributes=['id', 'kind'],
                           csv_file_location=csv_path.format('comp_cast_type'),
                           table_size=4))

    # name
    schema.add_table(Table('name', attributes=['id', 'name', 'imdb_index', 'imdb_id', 'gender', 'name_pcode_cf',
                                               'name_pcode_nf', 'surname_pcode', 'md5sum'],
                           csv_file_location=csv_path.format('name'),
                           table_size=4167491))

    # aka_name
    schema.add_table(Table('aka_name', attributes=['id', 'person_id', 'name', 'imdb_index', 'name_pcode_cf',
                                                   'name_pcode_nf', 'surname_pcode', 'md5sum'],
                           csv_file_location=csv_path.format('aka_name'),
                           table_size=901343))

    # movie_link
    schema.add_table(Table('movie_link', attributes=['id', 'movie_id', 'linked_movie_id', 'link_type_id'],
                           csv_file_location=csv_path.format('movie_link'),
                           table_size=29997))

    # link_type, no relationships
    schema.add_table(Table('link_type', attributes=['id', 'link'],
                           csv_file_location=csv_path.format('link_type'),
                           table_size=18))


    # movie_keyword
    schema.add_table(Table('movie_keyword', attributes=['id', 'movie_id', 'keyword_id'],
                           csv_file_location=csv_path.format('movie_keyword'),
                           table_size=4523930))

    # keyword
    schema.add_table(Table('keyword', attributes=['id', 'keyword', 'phonetic_code'],
                           csv_file_location=csv_path.format('keyword'),
                           table_size=134170))

    # person_info
    schema.add_table(Table('person_info', attributes=['id', 'person_id', 'info_type_id', 'info', 'note'],
                           csv_file_location=csv_path.format('person_info'),
                           irrelevant_attributes=['info', 'note'],
                           table_size=2963664))

    # movie_companies
    schema.add_table(Table('movie_companies', attributes=['id', 'movie_id', 'company_id', 'company_type_id', 'note'],
                           csv_file_location=csv_path.format('movie_companies'),
                           irrelevant_attributes=['note'],
                           no_compression=['company_id', 'company_type_id'],
                           table_size=2609129))

    # company_name
    schema.add_table(Table('company_name', attributes=['id', 'name', 'country_code', 'imdb_id', 'name_pcode_nf',
                                                       'name_pcode_sf', 'md5sum'],
                           irrelevant_attributes=['country_code', 'imdb_id', 'name_pcode_nf', 'name_pcode_sf', 'md5sum'],
                           csv_file_location=csv_path.format('company_name'),
                           table_size=234997))

    # company_type
    schema.add_table(Table('company_type', attributes=['id', 'kind'],
                           csv_file_location=csv_path.format('company_type'),
                           table_size=4))

    # aka_title
    schema.add_table(Table('aka_title', attributes=['id', 'movie_id', 'title', 'imdb_index', 'kind_id',
                                                    'production_year', 'phonetic_code', 'episode_of_id', 'season_nr',
                                                    'episode_nr', 'note', 'md5sum'],
                           irrelevant_attributes=['imdb_index', 'note', 'md5sum'],
                           csv_file_location=csv_path.format('aka_title'),
                           table_size=361472))

    # kind_type
    schema.add_table(Table('kind_type', attributes=['id', 'kind'],
                           csv_file_location=csv_path.format('kind_type'),
                           table_size=7))

    # relationships

    # title
    # omit self-join for now
    # schema.add_relationship('title', 'episode_of_id', 'title', 'id')
    schema.add_relationship('title', 'kind_id', 'kind_type', 'id')

    # movie_info_idx
    schema.add_relationship('movie_info_idx', 'info_type_id', 'info_type', 'id')
    schema.add_relationship('movie_info_idx', 'movie_id', 'title', 'id')

    # movie_info
    schema.add_relationship('movie_info', 'info_type_id', 'info_type', 'id')
    schema.add_relationship('movie_info', 'movie_id', 'title', 'id')

    # info_type, no relationships

    # cast_info
    schema.add_relationship('cast_info', 'movie_id', 'title', 'id')
    schema.add_relationship('cast_info', 'person_id', 'name', 'id')
    schema.add_relationship('cast_info', 'person_role_id', 'char_name', 'id')
    schema.add_relationship('cast_info', 'role_id', 'role_type', 'id')

    # char_name, no relationships

    # role_type, no relationships

    # complete_cast
    schema.add_relationship('complete_cast', 'movie_id', 'title', 'id')
    schema.add_relationship('complete_cast', 'status_id', 'comp_cast_type', 'id')
    schema.add_relationship('complete_cast', 'subject_id', 'comp_cast_type', 'id')

    # comp_cast_type, no relationships

    # name, no relationships

    # aka_name
    schema.add_relationship('aka_name', 'person_id', 'name', 'id')

    # movie_link, is empty
    schema.add_relationship('movie_link', 'link_type_id', 'link_type', 'id')
    schema.add_relationship('movie_link', 'linked_movie_id', 'title', 'id')
    schema.add_relationship('movie_link', 'movie_id', 'title', 'id')

    # link_type, no relationships

    # movie_keyword
    schema.add_relationship('movie_keyword', 'keyword_id', 'keyword', 'id')
    schema.add_relationship('movie_keyword', 'movie_id', 'title', 'id')

    # keyword, no relationships

    # person_info
    schema.add_relationship('person_info', 'info_type_id', 'info_type', 'id')
    schema.add_relationship('person_info', 'person_id', 'name', 'id')

    # movie_companies
    schema.add_relationship('movie_companies', 'company_id', 'company_name', 'id')
    schema.add_relationship('movie_companies', 'company_type_id', 'company_type', 'id')
    schema.add_relationship('movie_companies', 'movie_id', 'title', 'id')

    # company_name, no relationships

    # company_type, no relationships

    # aka_title
    schema.add_relationship('aka_title', 'movie_id', 'title', 'id')
    schema.add_relationship('aka_title', 'kind_id', 'kind_type', 'id')

    # kind_type, no relationships

    return schema
