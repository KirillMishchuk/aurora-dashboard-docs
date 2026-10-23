{{header}}
## Your role: finder f — external API contract

The PR changes server code that talks to OpenStack or Ceph RGW. These changed files are in scope:

{{finder_f_files}}

Check every changed call to OpenStack (`service("<name>")…`) or to Ceph RGW through the S3 client (`Storage/clients`, `Storage/routers/ceph`) in them, and every changed Zod schema describing an API response, against the official references — read them verbatim as your agent instructions describe, never from memory. Put each doc quote with its URL in `evidence`: that is what lets the scorer verify a candidate instead of guessing.
{{candidates}}
{{output}}
