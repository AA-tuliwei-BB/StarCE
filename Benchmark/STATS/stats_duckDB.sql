CREATE SEQUENCE users_id_seq START 1;

CREATE TABLE users (
    Id INTEGER PRIMARY KEY DEFAULT nextval('users_id_seq'),
    Reputation INTEGER,
    CreationDate TIMESTAMP,
    Views INTEGER,
    UpVotes INTEGER,
    DownVotes INTEGER
);

CREATE SEQUENCE posts_id_seq START 1;

CREATE TABLE posts (
    Id INTEGER PRIMARY KEY DEFAULT nextval('posts_id_seq'),
    PostTypeId SMALLINT,
    CreationDate TIMESTAMP,
    Score INTEGER,
    ViewCount INTEGER,
    OwnerUserId INTEGER,
    AnswerCount INTEGER,
    CommentCount INTEGER,
    FavoriteCount INTEGER,
    LastEditorUserId INTEGER
);

CREATE SEQUENCE postLinks_id_seq START 1;

CREATE TABLE postLinks (
    Id INTEGER PRIMARY KEY DEFAULT nextval('postLinks_id_seq'),
    CreationDate TIMESTAMP,
    PostId INTEGER,
    RelatedPostId INTEGER,
    LinkTypeId SMALLINT
);

CREATE SEQUENCE postHistory_id_seq START 1;

CREATE TABLE postHistory (
    Id INTEGER PRIMARY KEY DEFAULT nextval('postHistory_id_seq'),
    PostHistoryTypeId SMALLINT,
    PostId INTEGER,
    CreationDate TIMESTAMP,
    UserId INTEGER
);

CREATE SEQUENCE comments_id_seq START 1;

CREATE TABLE comments (
    Id INTEGER PRIMARY KEY DEFAULT nextval('comments_id_seq'),
    PostId INTEGER,
    Score SMALLINT,
    CreationDate TIMESTAMP,
    UserId INTEGER
);

CREATE SEQUENCE votes_id_seq START 1;

CREATE TABLE votes (
    Id INTEGER PRIMARY KEY DEFAULT nextval('votes_id_seq'),
    PostId INTEGER,
    VoteTypeId SMALLINT,
    CreationDate TIMESTAMP,
    UserId INTEGER,
    BountyAmount SMALLINT
);

CREATE SEQUENCE badges_id_seq START 1;

CREATE TABLE badges (
    Id INTEGER PRIMARY KEY DEFAULT nextval('badges_id_seq'),
    UserId INTEGER,
    Date TIMESTAMP
);

CREATE SEQUENCE tags_id_seq START 1;

CREATE TABLE tags (
    Id INTEGER PRIMARY KEY DEFAULT nextval('tags_id_seq'),
    Count INTEGER,
    ExcerptPostId INTEGER
);