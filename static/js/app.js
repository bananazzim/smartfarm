document.addEventListener("DOMContentLoaded", () => {
  const toggle = document.getElementById("menu-toggle");
  const header = document.getElementById("site-header");
  const navigation = document.getElementById("primary-navigation");
  if (toggle && header && navigation) {
    const closeMenu = (returnFocus = false) => {
      header.classList.remove("menu-open");
      document.body.classList.remove("menu-open");
      toggle.setAttribute("aria-expanded", "false");
      toggle.setAttribute("aria-label", "메뉴 열기");
      if (returnFocus) toggle.focus();
    };

    toggle.addEventListener("click", () => {
      const opened = header.classList.toggle("menu-open");
      document.body.classList.toggle("menu-open", opened);
      toggle.setAttribute("aria-expanded", String(opened));
      toggle.setAttribute("aria-label", opened ? "메뉴 닫기" : "메뉴 열기");
      if (opened) {
        window.requestAnimationFrame(() => navigation.querySelector("a")?.focus({ preventScroll: true }));
      }
    });
    navigation.addEventListener("click", (event) => {
      if (event.target instanceof Element && event.target.closest("a")) closeMenu();
    });
    document.addEventListener("keydown", (event) => {
      if (!header.classList.contains("menu-open")) return;
      if (event.key === "Escape") {
        closeMenu(true);
        return;
      }
      if (event.key !== "Tab") return;

      const links = [...navigation.querySelectorAll("a[href]")];
      const first = links[0];
      const last = links[links.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    });
    window.addEventListener("resize", () => {
      if (window.innerWidth > 1100 && header.classList.contains("menu-open")) closeMenu();
    });
    const updateHeader = () => {
      if (header.classList.contains("site-header-overlay")) {
        header.classList.toggle("is-scrolled", window.scrollY > 20);
      }
    };
    updateHeader();
    window.addEventListener("scroll", updateHeader, { passive: true });
  }
  document.querySelectorAll(".file-input input[type=file]").forEach((input) => {
    input.addEventListener("change", () => {
      const label = input.closest(".file-input");
      const text = label && label.querySelector("span");
      if (text && input.files.length) text.textContent = input.files[0].name;
    });
  });

  document.querySelectorAll("[data-gallery-viewport]").forEach((viewport) => {
    const track = viewport.querySelector("[data-gallery-track]");
    const previous = viewport.parentElement.querySelector("[data-gallery-prev]");
    const next = viewport.parentElement.querySelector("[data-gallery-next]");
    const current = viewport.parentElement.querySelector("[data-gallery-current]");
    const total = viewport.parentElement.querySelector("[data-gallery-total]");
    const cards = [...(track?.querySelectorAll(".gso-use-case-card") ?? [])];

    if (!track || !previous || !next || !current || !total || cards.length < 2) return;

    total.textContent = String(cards.length).padStart(2, "0");

    const cloneCount = Math.min(5, cards.length);
    const cloneCard = (card) => {
      const clone = card.cloneNode(true);
      clone.setAttribute("aria-hidden", "true");
      clone.setAttribute("tabindex", "-1");
      clone.inert = true;
      return clone;
    };
    const leadingClones = document.createDocumentFragment();
    const trailingClones = document.createDocumentFragment();
    cards.slice(-cloneCount).forEach((card) => leadingClones.append(cloneCard(card)));
    cards.slice(0, cloneCount).forEach((card) => trailingClones.append(cloneCard(card)));
    track.prepend(leadingClones);
    track.append(trailingClones);

    const allCards = [...track.querySelectorAll(".gso-use-case-card")];
    track.addEventListener("error", (event) => {
      const image = event.target;
      if (!(image instanceof HTMLImageElement) || !image.matches(".gso-use-case-image img")) return;
      image.classList.add("is-broken");
      image.closest(".gso-use-case-image")?.classList.add("is-image-unavailable");
    }, true);
    const positiveModulo = (value, divisor) => ((value % divisor) + divisor) % divisor;
    const logicalIndex = (physicalIndex) => positiveModulo(physicalIndex - cloneCount, cards.length);
    const scrollLeftFor = (card) => viewport.scrollLeft + card.getBoundingClientRect().left - viewport.getBoundingClientRect().left;
    const jumpToCard = (card) => {
      const previousBehavior = viewport.style.scrollBehavior;
      viewport.style.scrollBehavior = "auto";
      viewport.scrollLeft = scrollLeftFor(card);
      viewport.style.scrollBehavior = previousBehavior;
    };
    const nearestPhysicalIndex = () => {
      const viewportLeft = viewport.getBoundingClientRect().left;
      return allCards.reduce((nearest, card, index) => {
        const distance = Math.abs(card.getBoundingClientRect().left - viewportLeft);
        return distance < nearest.distance ? { index, distance } : nearest;
      }, { index: cloneCount, distance: Number.POSITIVE_INFINITY }).index;
    };

    let activeIndex = 0;
    let activePhysicalIndex = cloneCount;
    let targetIndex = 0;
    let targetPhysicalIndex = cloneCount;
    const queuedSteps = [];
    let animating = false;
    let settleTimer;

    const updateCounter = () => {
      const index = logicalIndex(nearestPhysicalIndex());
      current.textContent = String(index + 1).padStart(2, "0");
    };

    const finishScroll = () => {
      window.clearTimeout(settleTimer);
      if (animating) {
        activeIndex = targetIndex;
        activePhysicalIndex = cloneCount + activeIndex;
        if (targetPhysicalIndex !== activePhysicalIndex) {
          jumpToCard(allCards[activePhysicalIndex]);
        }
        animating = false;
      } else {
        const nearestIndex = nearestPhysicalIndex();
        activeIndex = logicalIndex(nearestIndex);
        activePhysicalIndex = cloneCount + activeIndex;
        if (nearestIndex !== activePhysicalIndex) {
          jumpToCard(allCards[activePhysicalIndex]);
        }
      }
      updateCounter();
      startNextStep();
    };

    const startNextStep = () => {
      if (animating || queuedSteps.length === 0) return;
      const direction = queuedSteps.shift();
      targetIndex = positiveModulo(activeIndex + direction, cards.length);
      targetPhysicalIndex = activePhysicalIndex + direction;
      if (activeIndex === cards.length - 1 && direction > 0) {
        targetPhysicalIndex = cloneCount + cards.length;
      } else if (activeIndex === 0 && direction < 0) {
        targetPhysicalIndex = cloneCount - 1;
      }
      animating = true;
      const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      viewport.scrollTo({
        left: scrollLeftFor(allCards[targetPhysicalIndex]),
        behavior: reduceMotion ? "auto" : "smooth",
      });
      if (reduceMotion) window.setTimeout(finishScroll, 0);
    };

    const queueStep = (direction) => {
      if (!animating && settleTimer) finishScroll();
      queuedSteps.push(direction);
      startNextStep();
    };

    jumpToCard(allCards[cloneCount]);
    previous.disabled = false;
    next.disabled = false;
    previous.addEventListener("click", () => queueStep(-1));
    next.addEventListener("click", () => queueStep(1));
    viewport.addEventListener("scroll", () => {
      updateCounter();
      window.clearTimeout(settleTimer);
      settleTimer = window.setTimeout(finishScroll, 140);
    }, { passive: true });
    viewport.addEventListener("scrollend", finishScroll);
    viewport.addEventListener("keydown", (event) => {
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      event.preventDefault();
      queueStep(event.key === "ArrowLeft" ? -1 : 1);
    });
    window.addEventListener("resize", () => {
      window.clearTimeout(settleTimer);
      activePhysicalIndex = cloneCount + activeIndex;
      jumpToCard(allCards[activePhysicalIndex]);
      updateCounter();
    });

    let dragStart = null;
    let suppressClick = false;
    let suppressClickTimer;
    viewport.addEventListener("pointerdown", (event) => {
      if (!event.isPrimary || (event.pointerType === "mouse" && event.button !== 0)) return;
      dragStart = {
        x: event.clientX,
        y: event.clientY,
        scrollLeft: viewport.scrollLeft,
        pointerId: event.pointerId,
        pointerType: event.pointerType,
        dragging: false,
      };
    });
    viewport.addEventListener("pointermove", (event) => {
      if (!dragStart || event.pointerId !== dragStart.pointerId) return;
      const distance = event.clientX - dragStart.x;
      const verticalDistance = event.clientY - dragStart.y;
      if (Math.abs(distance) <= 8 || Math.abs(distance) <= Math.abs(verticalDistance)) return;
      if (dragStart.pointerType === "mouse" && !dragStart.dragging) {
        dragStart.dragging = true;
        event.preventDefault();
        viewport.classList.add("is-dragging");
        viewport.setPointerCapture(event.pointerId);
      }
      suppressClick = true;
      window.clearTimeout(suppressClickTimer);
      suppressClickTimer = window.setTimeout(() => {
        suppressClick = false;
      }, 500);
      if (dragStart.pointerType === "mouse") {
        viewport.scrollLeft = dragStart.scrollLeft - distance;
      }
    });
    const endDrag = (event) => {
      if (!dragStart || (event && event.pointerId !== dragStart.pointerId)) return;
      dragStart = null;
      viewport.classList.remove("is-dragging");
    };
    viewport.addEventListener("pointerup", endDrag);
    viewport.addEventListener("pointercancel", endDrag);
    viewport.addEventListener("click", (event) => {
      if (!suppressClick) return;
      event.preventDefault();
      event.stopPropagation();
      suppressClick = false;
      window.clearTimeout(suppressClickTimer);
    }, true);
    updateCounter();
  });

  const snapshot = document.querySelector(".dashboard-metrics");
  if (snapshot) {
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    const canAnimateSnapshot = !reducedMotion.matches && "IntersectionObserver" in window;
    const sparklineConfigs = [
      { name: "temperature", dataId: "snapshot-temperature-series" },
      { name: "humidity", dataId: "snapshot-humidity-series" },
    ];
    const sparklinePaths = [];
    const measureScreenPath = (svg, path, pathLength) => {
      const bounds = svg.getBoundingClientRect();
      const viewBox = svg.viewBox.baseVal;
      const scaleX = bounds.width / viewBox.width;
      const scaleY = bounds.height / viewBox.height;
      const sampleCount = Math.max(1, Math.ceil(pathLength * 4));
      const samples = [{ pathDistance: 0, screenDistance: 0 }];
      let screenPathLength = 0;
      let previousPoint = path.getPointAtLength(0);

      for (let index = 1; index <= sampleCount; index += 1) {
        const pathDistance = (pathLength * index) / sampleCount;
        const point = path.getPointAtLength(pathDistance);
        screenPathLength += Math.hypot(
          (point.x - previousPoint.x) * scaleX,
          (point.y - previousPoint.y) * scaleY,
        );
        samples.push({ pathDistance, screenDistance: screenPathLength });
        previousPoint = point;
      }

      return { samples, screenPathLength, scaleX, scaleY, width: bounds.width, height: bounds.height };
    };
    const pathDistanceAtScreenDistance = (metrics, screenDistance) => {
      const target = Math.max(0, Math.min(screenDistance, metrics.screenPathLength));
      let low = 0;
      let high = metrics.samples.length - 1;
      while (low + 1 < high) {
        const middle = Math.floor((low + high) / 2);
        if (metrics.samples[middle].screenDistance < target) low = middle;
        else high = middle;
      }
      const start = metrics.samples[low];
      const end = metrics.samples[high];
      const segmentLength = end.screenDistance - start.screenDistance;
      const fraction = segmentLength
        ? (target - start.screenDistance) / segmentLength
        : 0;
      return start.pathDistance + (end.pathDistance - start.pathDistance) * fraction;
    };
    sparklineConfigs.forEach(({ name, dataId }) => {
      const svg = snapshot.querySelector(`[data-sparkline="${name}"]`);
      const data = snapshot.querySelector(`#${dataId}`);
      const path = svg?.querySelector(".snapshot-sparkline-path");
      const dot = svg?.querySelector(".snapshot-sparkline-dot");
      if (!svg || !data || !path) return;

      const values = JSON.parse(data.textContent);
      if (!Array.isArray(values) || values.length < 2 || !values.every(Number.isFinite)) {
        svg.hidden = true;
        return;
      }

      const minimum = Math.min(...values);
      const range = Math.max(...values) - minimum || 1;
      const points = values.map((value, index) => {
        const x = 4 + (index / (values.length - 1)) * 112;
        const y = 26 - ((value - minimum) / range) * 20;
        return `${x.toFixed(2)},${y.toFixed(2)}`;
      });
      path.setAttribute("d", `M ${points.join(" L ")}`);

      const pathLength = path.getTotalLength();
      const firstPoint = path.getPointAtLength(0);
      const lastPoint = path.getPointAtLength(pathLength);
      const metrics = measureScreenPath(svg, path, pathLength);
      const maskId = `snapshot-sparkline-gap-${name}`;
      const defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
      const mask = document.createElementNS("http://www.w3.org/2000/svg", "mask");
      mask.id = maskId;
      mask.setAttribute("maskUnits", "userSpaceOnUse");
      mask.setAttribute("x", "0");
      mask.setAttribute("y", "0");
      mask.setAttribute("width", "120");
      mask.setAttribute("height", "30");
      const maskBackground = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      maskBackground.setAttribute("width", "120");
      maskBackground.setAttribute("height", "30");
      maskBackground.setAttribute("fill", "white");
      const gapMask = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      gapMask.setAttribute("y", "0");
      gapMask.setAttribute("height", "30");
      gapMask.setAttribute("fill", "black");
      mask.append(maskBackground, gapMask);
      defs.append(mask);
      svg.prepend(defs);
      path.setAttribute("mask", `url(#${maskId})`);
      const sparkline = {
        svg, path, gapMask, dot, pathLength, firstPoint, lastPoint, metrics,
      };
      sparkline.tailLength = 42;
      sparkline.gapLength = metrics.screenPathLength * 0.4;
      sparkline.mainLength = Math.max(
        1,
        metrics.screenPathLength - sparkline.gapLength - sparkline.tailLength,
      );
      const updateGapMask = () => {
        const gapStart = path.getPointAtLength(pathDistanceAtScreenDistance(
          sparkline.metrics,
          sparkline.mainLength,
        ));
        const gapEnd = path.getPointAtLength(pathDistanceAtScreenDistance(
          sparkline.metrics,
          sparkline.mainLength + sparkline.gapLength,
        ));
        const capWidth = 1.1 / sparkline.metrics.scaleX;
        gapMask.setAttribute("x", String(Math.min(gapStart.x, gapEnd.x) - capWidth));
        gapMask.setAttribute("width", String(
          Math.abs(gapEnd.x - gapStart.x) + capWidth * 2,
        ));
      };
      updateGapMask();
      if (dot) {
        dot.setAttribute("cx", String(lastPoint.x));
        dot.setAttribute("cy", String(lastPoint.y));
      }
      path.style.strokeDasharray = `${metrics.screenPathLength} ${metrics.screenPathLength}`;
      path.style.strokeDashoffset = canAnimateSnapshot ? String(metrics.screenPathLength) : "0";

      if (canAnimateSnapshot) {
        if (dot) {
          dot.setAttribute("cx", String(firstPoint.x));
          dot.setAttribute("cy", String(firstPoint.y));
        }
        sparklinePaths.push(sparkline);
      } else {
        dot?.classList.add("is-complete");
      }
    });

    if (canAnimateSnapshot) {
      const refreshSparklineMetrics = () => {
        sparklinePaths.forEach((sparkline) => {
          const { svg, path, dot, pathLength, gapMask } = sparkline;
          const bounds = svg.getBoundingClientRect();
          if (
            bounds.width === sparkline.metrics.width
            && bounds.height === sparkline.metrics.height
          ) return;
          sparkline.metrics = measureScreenPath(svg, path, pathLength);
          sparkline.gapLength = sparkline.metrics.screenPathLength * 0.30;
          sparkline.mainLength = Math.max(
            1,
            sparkline.metrics.screenPathLength - sparkline.gapLength - sparkline.tailLength,
          );
          const gapStart = path.getPointAtLength(pathDistanceAtScreenDistance(
            sparkline.metrics,
            sparkline.mainLength,
          ));
          const gapEnd = path.getPointAtLength(pathDistanceAtScreenDistance(
            sparkline.metrics,
            sparkline.mainLength + sparkline.gapLength,
          ));
          const capWidth = 1.1 / sparkline.metrics.scaleX;
          gapMask.setAttribute("x", String(Math.min(gapStart.x, gapEnd.x) - capWidth));
          gapMask.setAttribute("width", String(
            Math.abs(gapEnd.x - gapStart.x) + capWidth * 2,
          ));
          if (dot?.classList.contains("is-complete")) {
            path.style.strokeDasharray = `${sparkline.metrics.screenPathLength} ${sparkline.metrics.screenPathLength}`;
            path.style.strokeDashoffset = "0";
          } else if (!dot?.classList.contains("is-active")) {
            path.style.strokeDasharray = `${sparkline.metrics.screenPathLength} ${sparkline.metrics.screenPathLength}`;
            path.style.strokeDashoffset = String(sparkline.metrics.screenPathLength);
          }
        });
      };
      if ("ResizeObserver" in window) {
        const sparklineResizeObserver = new ResizeObserver(refreshSparklineMetrics);
        sparklinePaths.forEach(({ svg }) => sparklineResizeObserver.observe(svg));
      } else {
        window.addEventListener("resize", refreshSparklineMetrics);
      }

      snapshot.classList.add("has-reveal");
      const cards = [...snapshot.querySelectorAll(".stat-card")];
      cards.forEach((card, index) => {
        card.style.setProperty("--snapshot-delay", `${150 + index * 110}ms`);
      });

      const countUps = [...snapshot.querySelectorAll("[data-count-up]")].map((element) => {
        const text = element.textContent.trim();
        const finalValue = Number(text);
        if (!Number.isFinite(finalValue)) return null;
        return {
          element,
          finalValue,
          decimals: (text.split(".")[1] ?? "").length,
        };
      }).filter(Boolean);

      const animateCount = ({ element, finalValue, decimals }) => {
        const startedAt = performance.now();
        const duration = 1000;
        element.textContent = (0).toFixed(decimals);

        const frame = (now) => {
          const progress = Math.min((now - startedAt) / duration, 1);
          const eased = 1 - (1 - progress) ** 3;
          element.textContent = (finalValue * eased).toFixed(decimals);
          if (progress < 1) window.requestAnimationFrame(frame);
        };
        window.requestAnimationFrame(frame);
      };

      const revealThreshold = 0.3;
      const drawSparkline = (sparkline) => {
        const { path, dot, pathLength, firstPoint, lastPoint } = sparkline;
        const startedAt = performance.now();
        const duration = 1050;
        dot?.classList.add("is-active");

        const frame = (now) => {
          const progress = Math.min((now - startedAt) / duration, 1);
          const eased = 1 - (1 - progress) ** 3;
          const { metrics } = sparkline;
          const screenDistance = metrics.screenPathLength * eased;
          const pathDistance = pathDistanceAtScreenDistance(metrics, screenDistance);
          const point = progress === 1 ? lastPoint : path.getPointAtLength(pathDistance);
          path.style.strokeDasharray = `${metrics.screenPathLength} ${metrics.screenPathLength}`;
          path.style.strokeDashoffset = String(metrics.screenPathLength - screenDistance);

          if (dot) {
            const markerPoint = progress === 0 ? firstPoint : point;
            dot.setAttribute("cx", String(markerPoint.x));
            dot.setAttribute("cy", String(markerPoint.y));
          }

          if (progress < 1) {
            window.requestAnimationFrame(frame);
          } else {
            dot?.classList.remove("is-active");
            dot?.classList.add("is-complete");
          }
        };

        window.requestAnimationFrame(frame);
      };

      const finishSparklines = () => {
        sparklinePaths.forEach((sparkline) => {
          const { path, dot, lastPoint, metrics } = sparkline;
          path.style.strokeDasharray = `${metrics.screenPathLength} ${metrics.screenPathLength}`;
          path.style.strokeDashoffset = "0";
          dot?.setAttribute("cx", String(lastPoint.x));
          dot?.setAttribute("cy", String(lastPoint.y));
          dot?.classList.remove("is-active");
          dot?.classList.add("is-complete");
        });
      };

      const observer = new IntersectionObserver((entries) => {
        if (!entries.some((entry) => (
          entry.target === snapshot
          && entry.isIntersecting
          && entry.intersectionRatio >= revealThreshold
        ))) return;
        observer.unobserve(snapshot);
        snapshot.classList.add("is-visible");

        if (reducedMotion.matches) {
          finishSparklines();
          return;
        }
        countUps.forEach(({ element, decimals }) => {
          element.textContent = (0).toFixed(decimals);
        });
        window.setTimeout(() => {
          if (reducedMotion.matches) {
            countUps.forEach(({ element, finalValue, decimals }) => {
              element.textContent = finalValue.toFixed(decimals);
            });
            return;
          }
          countUps.forEach(animateCount);
        }, 350);
        window.setTimeout(() => {
          if (reducedMotion.matches) return finishSparklines();
          window.requestAnimationFrame(() => sparklinePaths.forEach(drawSparkline));
        }, 500);
      }, { threshold: revealThreshold });
      observer.observe(snapshot);
    }
  }
});
