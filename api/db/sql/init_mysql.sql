create table mlas_entity_column(
id bigint not null auto_increment,
column_guid varchar(512),
gmt_create timestamp,
gmt_update timestamp,
primary key (id)
);

create table mlas_entity_column_mcd(
id bigint not null auto_increment,
column_guid varchar(512),
gmt_create timestamp,
gmt_update timestamp,
primary key (id)
);

create table mlas_lineage_column(
id bigint not null auto_increment,
upstream_columns varchar(512),
dst_column_guid varchar(512),
gmt_create timestamp,
gmt_update timestamp,
primary key (id)
);


select count(distinct column_guid) from mlas_entity_column;

truncate table mlas_entity_column;

select column_guid from mlas_entity_column
    order by id
    limit 0, 1000;