type SectionPlaceholderPageProps = {
  title: string;
  description: string;
};

export function SectionPlaceholderPage({ title, description }: SectionPlaceholderPageProps) {
  return (
    <article className="card section-page">
      <p className="eyebrow">Раздел админки</p>
      <h1>{title}</h1>
      <p className="summary">{description}</p>
    </article>
  );
}
