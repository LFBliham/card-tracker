CREATE TABLE sets (
	id 	integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
	year	smallint NOT NULL CHECK (year BETWEEN 1950 AND 2100),
	name	text NOT NULL,
	UNIQUE (year, name)
);
