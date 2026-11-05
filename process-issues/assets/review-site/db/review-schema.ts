import {sqliteTable,text,integer,index} from "drizzle-orm/sqlite-core";
export const publications=sqliteTable("publications",{
 publication_key:text("publication_key").primaryKey(),pr_key:text("pr_key").notNull(),
 project_key:text("project_key").notNull(),manifest:text("manifest").notNull(),created_at:text("created_at").notNull(),storage_prefix:text("storage_prefix")
},t=>[index("publication_pr").on(t.pr_key)]);
export const reviews=sqliteTable("reviews",{
 pr_key:text("pr_key").primaryKey(),project_key:text("project_key").notNull(),repository:text("repository").notNull(),
 pr_number:integer("pr_number").notNull(),version:integer("version").notNull(),current_key:text("current_key"),
 observation:text("observation").notNull(),updated_at:text("updated_at").notNull()
},t=>[index("review_project").on(t.project_key)]);

export const cleanupReceipts=sqliteTable("cleanup_receipts",{
 pr_key:text("pr_key").primaryKey(),project_key:text("project_key").notNull(),
 merged_at:text("merged_at").notNull(),started_at:text("started_at").notNull(),completed_at:text("completed_at")
});
export const uploadJobs=sqliteTable("upload_jobs",{
 storage_prefix:text("storage_prefix").primaryKey(),pr_key:text("pr_key").notNull(),project_key:text("project_key").notNull(),
 state:text("state").notNull(),created_at:text("created_at").notNull(),expires_at:text("expires_at").notNull()
},t=>[index("upload_pr").on(t.pr_key)]);
