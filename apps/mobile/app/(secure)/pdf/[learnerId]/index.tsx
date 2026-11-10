import { useEffect, useRef, useState } from "react";
import { router, useLocalSearchParams } from "expo-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as DocumentPicker from "expo-document-picker";
import { File, Paths } from "expo-file-system";
import { randomUUID } from "expo-crypto";
import type { Schema } from "@j26/api-client";
import { useApp } from "../../../../src/providers";
import { PagedList } from "../../../../src/paged-list";
import {
  Button,
  Card,
  ErrorNotice,
  Field,
  Message,
  Screen,
  Title,
} from "../../../../src/ui";
type Selection = {
  asset: DocumentPicker.DocumentPickerAsset;
  requestId: string;
  title?: string;
};
function removeCopy(asset?: DocumentPicker.DocumentPickerAsset) {
  if (asset?.uri.startsWith(Paths.cache.uri)) {
    try {
      const file = new File(asset.uri);
      if (file.exists) file.delete();
    } catch {
      /* OS may have already purged this private temporary copy. */
    }
  }
}
export default function PdfSources() {
  const { learnerId } = useLocalSearchParams<{ learnerId: string }>();
  const { api } = useApp();
  const cache = useQueryClient();
  const me = useQuery({ queryKey: ["me"], queryFn: api.me });
  const [selected, setSelected] = useState<Selection>();
  const ref = useRef<Selection | undefined>(undefined);
  const pending = useRef<Promise<unknown> | null>(null);
  const alive = useRef(true);
  const [title, setTitle] = useState("");
  const [message, setMessage] = useState("");
  const [picking, setPicking] = useState(false);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      const cleanup = () => removeCopy(ref.current?.asset);
      if (pending.current) void pending.current.then(cleanup, cleanup);
      else cleanup();
    };
  }, []);
  const open = (sourceId: string, runId?: string) =>
    router.push({
      pathname: "/pdf/[learnerId]/[sourceId]",
      params: { learnerId, sourceId, ...(runId ? { runId } : {}) },
    });
  const upload = useMutation({
    mutationFn: async () => {
      if (!selected) throw new Error("No selection");
      const record = { ...selected, title: selected.title ?? title.trim() };
      ref.current = record;
      setSelected(record);
      const operation = api.uploadPdf(
        learnerId,
        record.title,
        record.requestId,
        {
          uri: record.asset.uri,
          name: record.asset.name,
          type: "application/pdf",
        },
      );
      pending.current = operation;
      try {
        return await operation;
      } finally {
        pending.current = null;
      }
    },
    onSuccess: async (value) => {
      removeCopy(ref.current?.asset);
      ref.current = undefined;
      await cache.invalidateQueries({ queryKey: ["pdf-sources", learnerId] });
      await cache.invalidateQueries({ queryKey: ["materials", learnerId] });
      if (alive.current) {
        setSelected(undefined);
        setTitle("");
        open(value.source.id, value.extraction.id);
      }
    },
  });
  const pick = async () => {
    setPicking(true);
    setMessage("");
    try {
      const result = await DocumentPicker.getDocumentAsync({
        type: "application/pdf",
        copyToCacheDirectory: true,
        multiple: false,
      });
      if (result.canceled) return;
      const asset = result.assets[0];
      if (!asset) return;
      if (!alive.current) {
        removeCopy(asset);
        return;
      }
      const size = asset.size ?? new File(asset.uri).size;
      if (size <= 0 || size > 10 * 1024 * 1024) {
        removeCopy(asset);
        setMessage("Choose a nonempty PDF no larger than 10 MB.");
        return;
      }
      removeCopy(ref.current?.asset);
      const next = { asset, requestId: randomUUID() };
      ref.current = next;
      setSelected(next);
      upload.reset();
    } catch {
      setMessage("Could not open the PDF picker. Try again.");
    } finally {
      setPicking(false);
    }
  };
  return (
    <Screen>
      <Title>PDF sources</Title>
      <Message>
        Upload English PDFs up to 10 MB and 25 pages. Scanned pages may require
        OCR; this backend has no public OCR review workflow.
      </Message>
      {me.data?.roles.includes("educator") && (
        <Card>
          <Title>Upload & extract</Title>
          <Field
            label="Reading title"
            value={title}
            onChangeText={setTitle}
            maxLength={200}
            editable={!upload.isPending && !selected?.title}
          />
          <Button
            title={picking ? "Opening picker…" : "Select PDF"}
            secondary
            disabled={picking || upload.isPending}
            onPress={() => void pick()}
          />
          {selected && (
            <>
              <Message>Selected: {selected.asset.name}</Message>
              {selected.title && (
                <Message>
                  Retry preserves this upload request. Title and file stay
                  fixed; refresh sources after an uncertain response before
                  starting another upload.
                </Message>
              )}
              <Button
                title={
                  upload.isPending
                    ? "Uploading / extracting…"
                    : selected.title
                      ? "Retry same upload"
                      : "Upload & extract PDF"
                }
                disabled={upload.isPending || !title.trim() || picking}
                onPress={() => upload.mutate()}
              />
              <Button
                title="Clear selected copy"
                secondary
                disabled={upload.isPending}
                onPress={() => {
                  removeCopy(ref.current?.asset);
                  ref.current = undefined;
                  setSelected(undefined);
                  upload.reset();
                }}
              />
            </>
          )}
          <ErrorNotice error={upload.error} context="pdf" />
          {!!message && <Message>{message}</Message>}
        </Card>
      )}
      <PagedList<Schema<"SourceSummary">>
        queryKey={["pdf-sources", learnerId]}
        load={(c) => api.pdfSources(learnerId, c)}
        context="pdf"
        render={(source) => (
          <Card key={source.id}>
            <Title>{source.title}</Title>
            <Message>
              {source.latest_extraction?.status ?? "Not processed"} ·{" "}
              {source.byte_count} bytes
            </Message>
            <Button
              title="Open PDF extraction"
              onPress={() => open(source.id)}
            />
          </Card>
        )}
      />
    </Screen>
  );
}
