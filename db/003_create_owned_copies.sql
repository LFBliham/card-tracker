CREATE TABLE owned_copies (
	id		integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
	card_id		integer NOT NULL REFERENCES cards (id) ON DELETE RESTRICT,
	condition	text CHECK (condition IN ('mint', 'near_mint', 'excellent', 'good', 'fair', 'poor')),
	serial_number 	integer CHECK (serial_number > 0),
	storage		text,
	purchase_price 	numeric(8,2) CHECK (purchase_price >= 0),
	purchased_from	text,
	date_acquired	date,
	notes		text,
	created_at	timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX owned_copies_card_id_idx ON owned_copies (card_id);
