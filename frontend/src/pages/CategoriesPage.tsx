import { FormEvent, useState } from "react";
import { useCategories, useDeleteCategory, useSaveCategory } from "../api/hooks";
import type { Category, CategoryKind, ExpenseLevel } from "../api/types";
import { confirmDelete, ErrorText } from "../components/ui";

const GROUPS: { title: string; hint: string; match: (c: Category) => boolean }[] = [
  {
    title: "Gastos esenciales",
    hint: "Suman al costo de sobrevivir y al fondo de emergencia.",
    match: (c) => c.kind === "expense" && c.level === "essential",
  },
  {
    title: "Gastos de estilo de vida",
    hint: "Solo cuentan para el costo de vivir bien.",
    match: (c) => c.kind === "expense" && c.level === "lifestyle",
  },
  { title: "Ingresos", hint: "", match: (c) => c.kind === "income" },
];

export default function CategoriesPage() {
  const [showInactive, setShowInactive] = useState(false);
  const { data: categories } = useCategories(showInactive);
  const save = useSaveCategory();
  const remove = useDeleteCategory();

  return (
    <>
      <header className="page-header">
        <h1>Categorías</h1>
        <label className="row gap-sm small muted toggle">
          <input type="checkbox" checked={showInactive} onChange={(e) => setShowInactive(e.target.checked)} />
          Mostrar desactivadas
        </label>
      </header>

      <NewCategoryForm />
      <ErrorText error={save.error ?? remove.error} />

      <div className="three-col">
        {GROUPS.map((g) => (
          <section key={g.title} className="card">
            <h2>{g.title}</h2>
            {g.hint && <p className="muted small">{g.hint}</p>}
            <ul className="list">
              {categories?.filter(g.match).map((c) => (
                <li key={c.id} className={c.is_active ? "" : "archived"}>
                  <span>{c.name}</span>
                  <span className="row gap-sm">
                    {c.kind === "expense" && (
                      <button
                        className="link small"
                        title="Cambiar entre esencial y estilo de vida"
                        onClick={() =>
                          save.mutate({ id: c.id, level: c.level === "essential" ? "lifestyle" : "essential" })
                        }
                      >
                        {c.level === "essential" ? "→ estilo" : "→ esencial"}
                      </button>
                    )}
                    <button className="link small" onClick={() => save.mutate({ id: c.id, is_active: !c.is_active })}>
                      {c.is_active ? "Desactivar" : "Activar"}
                    </button>
                    <button
                      className="link small danger"
                      onClick={() => confirmDelete(c.name) && remove.mutate(c.id)}
                    >
                      Borrar
                    </button>
                  </span>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </>
  );
}

function NewCategoryForm() {
  const save = useSaveCategory();
  const [name, setName] = useState("");
  const [type, setType] = useState<"essential" | "lifestyle" | "income">("essential");

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    const kind: CategoryKind = type === "income" ? "income" : "expense";
    const level: ExpenseLevel | null = type === "income" ? null : type;
    save.mutate({ name, kind, level }, { onSuccess: () => setName("") });
  }

  return (
    <form className="card form" onSubmit={onSubmit}>
      <div className="grid-3">
        <label>
          Nueva categoría
          <input value={name} onChange={(e) => setName(e.target.value)} required maxLength={80} />
        </label>
        <label>
          Tipo
          <select value={type} onChange={(e) => setType(e.target.value as typeof type)}>
            <option value="essential">Gasto esencial</option>
            <option value="lifestyle">Gasto estilo de vida</option>
            <option value="income">Ingreso</option>
          </select>
        </label>
        <div className="align-end">
          <button className="btn" disabled={save.isPending}>
            Agregar
          </button>
        </div>
      </div>
      <ErrorText error={save.error} />
    </form>
  );
}
