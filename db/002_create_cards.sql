CREATE TABLE cards (
	id		integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
	set_id		integer NOT NULL REFERENCES sets (id) ON DELETE RESTRICT,
	card_number	text NOT NULL,
	card_name	text NOT NULL,
	subset		text,
	team 		text,
	variant		text NOT NULL DEFAULT 'Base',
	print_run	integer CHECK (print_run > 0),
	wishlisted	boolean NOT NULL DEFAULT false,
	UNIQUE (set_id, card_number, variant)
);
