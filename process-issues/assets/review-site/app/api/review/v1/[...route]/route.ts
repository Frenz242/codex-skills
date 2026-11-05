import {env} from "cloudflare:workers";
import {handleReview} from "../../../../../lib/review-service.mjs";
export const dynamic="force-dynamic";
export const GET=(r:Request)=>handleReview(r,env);
export const HEAD=GET;
export const POST=GET;
export const PATCH=GET;
