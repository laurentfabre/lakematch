import { useQuery, useSuspenseQuery, useMutation } from "@tanstack/react-query";
import type { UseQueryOptions, UseSuspenseQueryOptions, UseMutationOptions } from "@tanstack/react-query";
export class ApiError extends Error {
    status: number;
    statusText: string;
    body: unknown;
    constructor(status: number, statusText: string, body: unknown){
        super(`HTTP ${status}: ${statusText}`);
        this.name = "ApiError";
        this.status = status;
        this.statusText = statusText;
        this.body = body;
    }
}
export interface AgreementOut {
    agree: number;
    confusion: Record<string, number>;
    llm_opinions_in_queue: number;
    llm_unsure_on_labelled: number;
    pairs: number;
    rate?: number | null;
}
export interface FieldOut {
    left?: string | null;
    name: string;
    right?: string | null;
    same: boolean;
}
export interface HTTPValidationError {
    detail?: ValidationError[];
}
export interface LabelIn {
    decision: "match" | "no_match" | "unsure";
    l_id: string;
    r_id: string;
    reason: string;
}
export interface LabelOut {
    decision: string;
    is_match?: number | null;
    l_id: string;
    label_id: string;
    labelled_at: string;
    llm_label?: string | null;
    model_version?: string | null;
    p?: number | null;
    queue_reason?: string | null;
    r_id: string;
    reason: string;
    reviewer: string;
    run_id?: string | null;
    threshold?: number | null;
}
export interface LabelStatsOut {
    by_reviewer: Record<string, number>;
    complete_provenance: number;
    current: Record<string, number>;
    events: number;
    retracted: number;
}
export interface LabelsOut {
    labels: LabelOut[];
}
export interface ModelVersionOut {
    app_labels_used?: number | null;
    created_at?: string | null;
    evaluation?: string | null;
    f1?: number | null;
    human_labelled: number;
    human_precision?: number | null;
    human_recall?: number | null;
    label_source?: string | null;
    labels_train?: number | null;
    model_version: string;
    precision?: number | null;
    recall?: number | null;
    run_id?: string | null;
    threshold?: number | null;
}
export interface NextOut {
    items: QueueItemOut[];
}
export interface QuarantineOut {
    history: QuarantineRunOut[];
    latest?: QuarantineRunOut | null;
}
export interface QuarantineRunOut {
    created_at?: string | null;
    left: number;
    model_version: string;
    right: number;
    run_id: string;
}
export interface QueueDepthOut {
    labelled: number;
    model_version?: string | null;
    pending: number;
    pending_by_reason: Record<string, number>;
    total: number;
    total_by_reason: Record<string, number>;
}
export interface QueueItemOut {
    cand_rank?: number | null;
    cand_score?: number | null;
    distance: number;
    fields: FieldOut[];
    impact?: number | null;
    l_id: string;
    linked: boolean;
    llm_label?: string | null;
    llm_p_same?: number | null;
    model_version: string;
    p: number;
    queue_reason: string;
    r_id: string;
    rank: number;
    run_id: string;
    threshold: number;
}
export interface RetractIn {
    l_id: string;
    r_id: string;
    reason?: string;
}
export interface SessionOut {
    app_version: string;
    label_store: string;
    reviewer: string;
    source: string;
}
export interface StatsOut {
    agreement: AgreementOut;
    labels: LabelStatsOut;
    model_versions: ModelVersionOut[];
    quarantine: QuarantineOut;
    queue: QueueDepthOut;
}
export interface ValidationError {
    ctx?: Record<string, unknown>;
    input?: unknown;
    loc: (string | number)[];
    msg: string;
    type: string;
}
export interface VersionOut {
    version: string;
}
export interface ListLabelsParams {
    limit?: number;
}
export const listLabels = async (params?: ListLabelsParams, options?: RequestInit): Promise<{
    data: LabelsOut;
}> =>{
    const searchParams = new URLSearchParams();
    if (params?.limit != null) searchParams.set("limit", String(params?.limit));
    const queryString = searchParams.toString();
    const url = queryString ? `/api/labels?${queryString}` : "/api/labels";
    const res = await fetch(url, {
        ...options,
        method: "GET"
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export const listLabelsKey = (params?: ListLabelsParams)=>{
    return [
        "/api/labels",
        params
    ] as const;
};
export function useListLabels<TData = {
    data: LabelsOut;
}>(options?: {
    params?: ListLabelsParams;
    query?: Omit<UseQueryOptions<{
        data: LabelsOut;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useQuery({
        queryKey: listLabelsKey(options?.params),
        queryFn: ()=>listLabels(options?.params),
        ...options?.query
    });
}
export function useListLabelsSuspense<TData = {
    data: LabelsOut;
}>(options?: {
    params?: ListLabelsParams;
    query?: Omit<UseSuspenseQueryOptions<{
        data: LabelsOut;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useSuspenseQuery({
        queryKey: listLabelsKey(options?.params),
        queryFn: ()=>listLabels(options?.params),
        ...options?.query
    });
}
export interface AddLabelParams {
    "X-Forwarded-Host"?: string | null;
    "X-Forwarded-Preferred-Username"?: string | null;
    "X-Forwarded-User"?: string | null;
    "X-Forwarded-Email"?: string | null;
    "X-Request-Id"?: string | null;
    "X-Forwarded-Access-Token"?: string | null;
}
export const addLabel = async (data: LabelIn, params?: AddLabelParams, options?: RequestInit): Promise<{
    data: LabelOut;
}> =>{
    const res = await fetch("/api/labels", {
        ...options,
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            ...(params?.["X-Forwarded-Host"] != null && {
                "X-Forwarded-Host": params["X-Forwarded-Host"]
            }),
            ...(params?.["X-Forwarded-Preferred-Username"] != null && {
                "X-Forwarded-Preferred-Username": params["X-Forwarded-Preferred-Username"]
            }),
            ...(params?.["X-Forwarded-User"] != null && {
                "X-Forwarded-User": params["X-Forwarded-User"]
            }),
            ...(params?.["X-Forwarded-Email"] != null && {
                "X-Forwarded-Email": params["X-Forwarded-Email"]
            }),
            ...(params?.["X-Request-Id"] != null && {
                "X-Request-Id": params["X-Request-Id"]
            }),
            ...(params?.["X-Forwarded-Access-Token"] != null && {
                "X-Forwarded-Access-Token": params["X-Forwarded-Access-Token"]
            }),
            ...options?.headers
        },
        body: JSON.stringify(data)
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export function useAddLabel(options?: {
    mutation?: UseMutationOptions<{
        data: LabelOut;
    }, ApiError, {
        params: AddLabelParams;
        data: LabelIn;
    }>;
}) {
    return useMutation({
        mutationFn: (vars)=>addLabel(vars.data, vars.params),
        ...options?.mutation
    });
}
export interface RetractLabelParams {
    "X-Forwarded-Host"?: string | null;
    "X-Forwarded-Preferred-Username"?: string | null;
    "X-Forwarded-User"?: string | null;
    "X-Forwarded-Email"?: string | null;
    "X-Request-Id"?: string | null;
    "X-Forwarded-Access-Token"?: string | null;
}
export const retractLabel = async (data: RetractIn, params?: RetractLabelParams, options?: RequestInit): Promise<{
    data: LabelOut;
}> =>{
    const res = await fetch("/api/labels/retract", {
        ...options,
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            ...(params?.["X-Forwarded-Host"] != null && {
                "X-Forwarded-Host": params["X-Forwarded-Host"]
            }),
            ...(params?.["X-Forwarded-Preferred-Username"] != null && {
                "X-Forwarded-Preferred-Username": params["X-Forwarded-Preferred-Username"]
            }),
            ...(params?.["X-Forwarded-User"] != null && {
                "X-Forwarded-User": params["X-Forwarded-User"]
            }),
            ...(params?.["X-Forwarded-Email"] != null && {
                "X-Forwarded-Email": params["X-Forwarded-Email"]
            }),
            ...(params?.["X-Request-Id"] != null && {
                "X-Request-Id": params["X-Request-Id"]
            }),
            ...(params?.["X-Forwarded-Access-Token"] != null && {
                "X-Forwarded-Access-Token": params["X-Forwarded-Access-Token"]
            }),
            ...options?.headers
        },
        body: JSON.stringify(data)
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export function useRetractLabel(options?: {
    mutation?: UseMutationOptions<{
        data: LabelOut;
    }, ApiError, {
        params: RetractLabelParams;
        data: RetractIn;
    }>;
}) {
    return useMutation({
        mutationFn: (vars)=>retractLabel(vars.data, vars.params),
        ...options?.mutation
    });
}
export interface NextPairsParams {
    skip?: string[] | null;
    n?: number;
}
export const nextPairs = async (params?: NextPairsParams, options?: RequestInit): Promise<{
    data: NextOut;
}> =>{
    const searchParams = new URLSearchParams();
    if (params?.skip != null) params?.skip.forEach((v)=>searchParams.append("skip", String(v)));
    if (params?.n != null) searchParams.set("n", String(params?.n));
    const queryString = searchParams.toString();
    const url = queryString ? `/api/queue/next?${queryString}` : "/api/queue/next";
    const res = await fetch(url, {
        ...options,
        method: "GET"
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export const nextPairsKey = (params?: NextPairsParams)=>{
    return [
        "/api/queue/next",
        params
    ] as const;
};
export function useNextPairs<TData = {
    data: NextOut;
}>(options?: {
    params?: NextPairsParams;
    query?: Omit<UseQueryOptions<{
        data: NextOut;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useQuery({
        queryKey: nextPairsKey(options?.params),
        queryFn: ()=>nextPairs(options?.params),
        ...options?.query
    });
}
export function useNextPairsSuspense<TData = {
    data: NextOut;
}>(options?: {
    params?: NextPairsParams;
    query?: Omit<UseSuspenseQueryOptions<{
        data: NextOut;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useSuspenseQuery({
        queryKey: nextPairsKey(options?.params),
        queryFn: ()=>nextPairs(options?.params),
        ...options?.query
    });
}
export interface SessionParams {
    "X-Forwarded-Host"?: string | null;
    "X-Forwarded-Preferred-Username"?: string | null;
    "X-Forwarded-User"?: string | null;
    "X-Forwarded-Email"?: string | null;
    "X-Request-Id"?: string | null;
    "X-Forwarded-Access-Token"?: string | null;
}
export const session = async (params?: SessionParams, options?: RequestInit): Promise<{
    data: SessionOut;
}> =>{
    const res = await fetch("/api/session", {
        ...options,
        method: "GET",
        headers: {
            ...(params?.["X-Forwarded-Host"] != null && {
                "X-Forwarded-Host": params["X-Forwarded-Host"]
            }),
            ...(params?.["X-Forwarded-Preferred-Username"] != null && {
                "X-Forwarded-Preferred-Username": params["X-Forwarded-Preferred-Username"]
            }),
            ...(params?.["X-Forwarded-User"] != null && {
                "X-Forwarded-User": params["X-Forwarded-User"]
            }),
            ...(params?.["X-Forwarded-Email"] != null && {
                "X-Forwarded-Email": params["X-Forwarded-Email"]
            }),
            ...(params?.["X-Request-Id"] != null && {
                "X-Request-Id": params["X-Request-Id"]
            }),
            ...(params?.["X-Forwarded-Access-Token"] != null && {
                "X-Forwarded-Access-Token": params["X-Forwarded-Access-Token"]
            }),
            ...options?.headers
        }
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export const sessionKey = (params?: SessionParams)=>{
    return [
        "/api/session",
        params
    ] as const;
};
export function useSession<TData = {
    data: SessionOut;
}>(options?: {
    params?: SessionParams;
    query?: Omit<UseQueryOptions<{
        data: SessionOut;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useQuery({
        queryKey: sessionKey(options?.params),
        queryFn: ()=>session(options?.params),
        ...options?.query
    });
}
export function useSessionSuspense<TData = {
    data: SessionOut;
}>(options?: {
    params?: SessionParams;
    query?: Omit<UseSuspenseQueryOptions<{
        data: SessionOut;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useSuspenseQuery({
        queryKey: sessionKey(options?.params),
        queryFn: ()=>session(options?.params),
        ...options?.query
    });
}
export const stats = async (options?: RequestInit): Promise<{
    data: StatsOut;
}> =>{
    const res = await fetch("/api/stats", {
        ...options,
        method: "GET"
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export const statsKey = ()=>{
    return [
        "/api/stats"
    ] as const;
};
export function useStats<TData = {
    data: StatsOut;
}>(options?: {
    query?: Omit<UseQueryOptions<{
        data: StatsOut;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useQuery({
        queryKey: statsKey(),
        queryFn: ()=>stats(),
        ...options?.query
    });
}
export function useStatsSuspense<TData = {
    data: StatsOut;
}>(options?: {
    query?: Omit<UseSuspenseQueryOptions<{
        data: StatsOut;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useSuspenseQuery({
        queryKey: statsKey(),
        queryFn: ()=>stats(),
        ...options?.query
    });
}
export const version = async (options?: RequestInit): Promise<{
    data: VersionOut;
}> =>{
    const res = await fetch("/api/version", {
        ...options,
        method: "GET"
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export const versionKey = ()=>{
    return [
        "/api/version"
    ] as const;
};
export function useVersion<TData = {
    data: VersionOut;
}>(options?: {
    query?: Omit<UseQueryOptions<{
        data: VersionOut;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useQuery({
        queryKey: versionKey(),
        queryFn: ()=>version(),
        ...options?.query
    });
}
export function useVersionSuspense<TData = {
    data: VersionOut;
}>(options?: {
    query?: Omit<UseSuspenseQueryOptions<{
        data: VersionOut;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useSuspenseQuery({
        queryKey: versionKey(),
        queryFn: ()=>version(),
        ...options?.query
    });
}
