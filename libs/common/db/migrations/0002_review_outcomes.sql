-- Review items record the reviewer's decision, and notifications may concern
-- a whole application rather than one document.

ALTER TABLE review_items ADD COLUMN IF NOT EXISTS outcome text;

ALTER TABLE notifications RENAME COLUMN document_id TO subject_id;
