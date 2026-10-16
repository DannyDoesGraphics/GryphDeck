export function ScorePregame({ scene }) {
  const placeholderLogo = "/static/Teams/placeholder.png";
  const handleLogoError = ({ currentTarget }) => {
    if (currentTarget.getAttribute("src") !== placeholderLogo) {
      currentTarget.src = placeholderLogo;
    }
  };
  const teamNameStyle = (name) => ({
    position: "absolute",
    transform: "translate(-50%, -50%)",
    display: "flex",
    alignItems: "center",
    gap: "50px",
    width: "max-content",
    fontSize: `calc(50cqw / ${Math.max(name.length, 10)})`,
    fontWeight: 700,
    lineHeight: 1,
    whiteSpace: "nowrap",
    margin: 0,
  });
  const logoStyle = {
    display: "block",
    width: "175px",
    height: "auto",
    flexShrink: 0,
    objectFit: "contain",
    margin: 0,
  };
  const scoreStyle = {
    position: "absolute",
    top: "51%",
    transform: "translate(-50%, -50%)",
    fontSize: "22cqw",
    fontWeight: 400,
    lineHeight: 1,
    letterSpacing: "-0.06em",
  };

  return (
    <div
      className="score-pregame"
      style={{
        position: "relative",
        width: "min(100vw, calc(100vh * 16 / 9))",
        aspectRatio: "16 / 9",
        containerType: "inline-size",
        fontFamily: '"DM Sans", sans-serif',
        fontWeight: 700,
      }}
    >
      <img
        src="/static/bg-half.png"
        alt=""
        style={{ display: "block", width: "100%", height: "100%" }}
      />

      <div
        className="score-pregame-left"
        style={{ position: "absolute", inset: "0 50% 0 0", color: "#fff" }}
      >
        <div
          className="score-pregame-team-name"
          style={{
            ...teamNameStyle(scene.teams[0].name),
            left: "56%",
            top: "24%",
          }}
        >
          <span>{scene.teams[0].name}</span>
          <img
            src={`/static/Teams/${encodeURIComponent(scene.teams[0].name)}.png`}
            alt=""
            onError={handleLogoError}
            style={logoStyle}
          />
        </div>
        <div
          className="score-pregame-score"
          style={{ ...scoreStyle, left: "68%" }}
        >
          {String(scene.teams[0].score).padStart(2, "0")}
        </div>
      </div>

      <div
        className="score-pregame-right"
        style={{ position: "absolute", inset: "0 0 0 50%", color: "#221e1e" }}
      >
        <div
          className="score-pregame-score"
          style={{ ...scoreStyle, left: "32%" }}
        >
          {String(scene.teams[1].score).padStart(2, "0")}
        </div>
        <div
          className="score-pregame-team-name"
          style={{
            ...teamNameStyle(scene.teams[1].name),
            left: "44%",
            top: "76%",
          }}
        >
          <img
            src={`/static/Teams/${encodeURIComponent(scene.teams[1].name)}.png`}
            alt=""
            onError={handleLogoError}
            style={logoStyle}
          />
          <span>{scene.teams[1].name}</span>
        </div>
      </div>
    </div>
  );
}
