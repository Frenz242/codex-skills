import {sqliteTable,text,integer,index} from "drizzle-orm/sqlite-core";
export const publications=sqliteTable("publications",{
 publication_key:text("publication_key").primaryKey(),pr_key:text("pr_key").notNull(),
 project_key:text("project_key").notNull(),manifest:text("manifest").notNull(),created_at:text("created_at").notNull()
},t=>[index("publication_pr").on(t.pr_key)]);
export const reviews=sqliteTable("reviews",{
 pr_key:text("pr_key").primaryKey(),project_key:text("project_key").notNull(),repository:text("repository").notNull(),
 pr_number:integer("pr_number").notNull(),version:integer("version").notNull(),current_key:text("current_key"),
 observation:text("observation").notNull(),updated_at:text("updated_at").notNull()
},t=>[index("review_project").on(t.project_key)]);
