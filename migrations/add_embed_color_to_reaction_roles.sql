-- Add embed_color column to reaction_roles table
ALTER TABLE reaction_roles ADD COLUMN embed_color VARCHAR(7) DEFAULT NULL;

-- Update existing records to have blue color (#0099ff)
UPDATE reaction_roles SET embed_color = '#0099ff' WHERE embed_color IS NULL;